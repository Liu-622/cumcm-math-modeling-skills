#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from common import SCHEMA_VERSION, canonical_digest, digest, emit, now, project_relative, read_json, write_json


def files_under(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(item for item in path.rglob("*") if item.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a declared build in a new isolated project directory.")
    parser.add_argument("project")
    parser.add_argument("--plan", default="evidence/build_plan.json")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors: list[str] = []
    try:
        plan_path, _ = project_relative(project, args.plan, must_exist=True)
        plan = read_json(plan_path)
    except (OSError, ValueError) as exc:
        emit({"status": "FAIL", "errors": [str(exc)]})
        return 2
    copy_paths = plan.get("copy_paths", [])
    steps = plan.get("steps", [])
    artifacts = plan.get("artifacts", [])
    if not isinstance(copy_paths, list) or not copy_paths:
        errors.append("build plan copy_paths must be non-empty")
    if not isinstance(steps, list) or not steps:
        errors.append("build plan steps must be non-empty")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("build plan artifacts must be non-empty")
    run_id = now().replace(":", "").replace("+", "_") + "_" + uuid.uuid4().hex[:8]
    run_dir = project / "build" / "clean" / run_id
    workspace = run_dir / "workspace"
    log_path = run_dir / "build.log"
    run_dir.mkdir(parents=True, exist_ok=False)
    workspace.mkdir()
    source_snapshot: list[dict] = []
    command_records: list[dict] = []
    artifact_records: list[dict] = []
    try:
        seen: set[str] = set()
        for raw in copy_paths if isinstance(copy_paths, list) else []:
            source, relative = project_relative(project, str(raw), must_exist=True)
            if relative == "build" or relative.startswith("build/"):
                raise ValueError("build outputs cannot be copied as clean-build inputs")
            if source.is_symlink() or any(item.is_symlink() for item in source.rglob("*") if source.is_dir()):
                raise ValueError(f"symlinks are not allowed in clean-build inputs: {relative}")
            target = workspace / relative
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            for item in files_under(source):
                item_rel = item.relative_to(project).as_posix()
                if item_rel in seen:
                    continue
                seen.add(item_rel)
                copied = workspace / item_rel
                source_snapshot.append({"path": item_rel, "sha256": digest(item), "copy_sha256": digest(copied)})

        artifact_rels: list[str] = []
        for raw in artifacts if isinstance(artifacts, list) else []:
            target = (workspace / str(raw)).resolve()
            try:
                relative = target.relative_to(workspace).as_posix()
            except ValueError as exc:
                raise ValueError(f"artifact escapes clean workspace: {raw}") from exc
            if target.is_dir():
                raise ValueError(f"artifact must be a file: {raw}")
            if target.exists():
                target.unlink()
            artifact_rels.append(relative)

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        with log_path.open("w", encoding="utf-8") as log:
            for index, step in enumerate(steps if isinstance(steps, list) else []):
                if not isinstance(step, dict) or not isinstance(step.get("argv"), list) or not step["argv"]:
                    raise ValueError(f"step[{index}].argv must be a non-empty string list")
                raw_argv = step["argv"]
                if any(not isinstance(value, str) or not value for value in raw_argv):
                    raise ValueError(f"step[{index}].argv contains an invalid value")
                for value in raw_argv[1:]:
                    if Path(value).is_absolute():
                        raise ValueError(f"step[{index}] uses an absolute argument path: {value}")
                argv = [sys.executable if value == "{python}" else value for value in raw_argv]
                cwd_rel = str(step.get("cwd", "."))
                cwd = (workspace / cwd_rel).resolve()
                try:
                    cwd.relative_to(workspace)
                except ValueError as exc:
                    raise ValueError(f"step[{index}].cwd escapes clean workspace") from exc
                if not cwd.is_dir():
                    raise ValueError(f"step[{index}].cwd does not exist: {cwd_rel}")
                timeout = int(step.get("timeout_seconds", 900))
                started = now()
                proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
                log.write(f"STEP {index + 1}: {raw_argv!r}\nRETURN_CODE: {proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}\n")
                command_records.append({"argv": raw_argv, "cwd": cwd_rel, "started_at": started, "returncode": proc.returncode})
                if proc.returncode != 0:
                    errors.append(f"build step {index + 1} failed with return code {proc.returncode}")
                    break

        if not errors:
            for relative in artifact_rels:
                artifact = workspace / relative
                if not artifact.is_file():
                    errors.append(f"expected artifact was not rebuilt: {relative}")
                else:
                    stored_rel = artifact.relative_to(project).as_posix()
                    artifact_records.append({"path": stored_rel, "workspace_path": relative, "sha256": digest(artifact)})
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        errors.append(str(exc))
        if not log_path.exists():
            log_path.write_text(str(exc) + "\n", encoding="utf-8")

    record = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "run_clean_build.py",
        "run_id": run_id,
        "started_at": run_id.rsplit("_", 1)[0],
        "finished_at": now(),
        "plan_path": plan_path.relative_to(project).as_posix(),
        "plan_sha256": digest(plan_path),
        "clean_directory": run_dir.relative_to(project).as_posix(),
        "source_snapshot": source_snapshot,
        "commands": command_records,
        "dependencies": {"python": platform.python_version(), "platform": platform.platform()},
        "compile_log": log_path.relative_to(project).as_posix(),
        "compile_log_sha256": digest(log_path),
        "rebuilt_files": artifact_records,
        "errors": errors,
        "status": "PASS" if not errors and artifact_records else "FAIL",
    }
    record["record_hash"] = canonical_digest(record)
    write_json(project / "evidence/build_verification.json", record)
    emit(record)
    return 0 if record["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
