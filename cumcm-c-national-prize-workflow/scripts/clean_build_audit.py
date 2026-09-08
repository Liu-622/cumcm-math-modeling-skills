#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import canonical_digest, digest, emit, project_relative, read_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit evidence produced by run_clean_build.py.")
    parser.add_argument("project")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    record_path = project / "evidence/build_verification.json"
    errors: list[str] = []
    try:
        record = read_json(record_path)
    except (OSError, ValueError) as exc:
        emit({"status": "FAIL", "errors": [str(exc)]})
        return 2
    required = ["schema_version", "generated_by", "run_id", "plan_path", "plan_sha256", "clean_directory", "source_snapshot", "commands", "dependencies", "compile_log", "compile_log_sha256", "rebuilt_files", "status", "record_hash"]
    missing = [field for field in required if field not in record]
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    if record.get("generated_by") != "run_clean_build.py":
        errors.append("record was not produced by run_clean_build.py")
    claimed_hash = record.get("record_hash")
    unsigned = {key: value for key, value in record.items() if key != "record_hash"}
    if claimed_hash != canonical_digest(unsigned):
        errors.append("build record consistency hash mismatch")
    try:
        plan_path, _ = project_relative(project, str(record.get("plan_path", "")), must_exist=True)
        plan = read_json(plan_path)
        if digest(plan_path) != record.get("plan_sha256"):
            errors.append("build plan changed after execution")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        plan = {}
    try:
        clean_dir, _ = project_relative(project, str(record.get("clean_directory", "")), must_exist=True)
        if not clean_dir.is_dir() or clean_dir.parent != project / "build" / "clean":
            errors.append("clean_directory is not an isolated run directory")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        clean_dir = project
    for index, item in enumerate(record.get("source_snapshot", [])):
        try:
            source, relative = project_relative(project, item["path"], must_exist=True)
            copied = clean_dir / "workspace" / relative
            if not source.is_file() or digest(source) != item.get("sha256"):
                errors.append(f"source changed after build: {item.get('path')}")
            if not copied.is_file() or digest(copied) != item.get("copy_sha256"):
                errors.append(f"clean source copy mismatch: {item.get('path')}")
        except (KeyError, OSError, ValueError) as exc:
            errors.append(f"source_snapshot[{index}]: {exc}")
    planned_steps = plan.get("steps", []) if isinstance(plan, dict) else []
    commands = record.get("commands", [])
    if len(commands) != len(planned_steps):
        errors.append("not every declared build step completed")
    for index, command in enumerate(commands):
        if command.get("returncode") != 0:
            errors.append(f"command[{index}] did not succeed")
        if index < len(planned_steps):
            if command.get("argv") != planned_steps[index].get("argv") or command.get("cwd") != str(planned_steps[index].get("cwd", ".")):
                errors.append(f"command[{index}] differs from current build plan")
    try:
        log, _ = project_relative(project, str(record.get("compile_log", "")), must_exist=True)
        if digest(log) != record.get("compile_log_sha256"):
            errors.append("build log hash mismatch")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    rebuilt = record.get("rebuilt_files", [])
    planned_artifacts = {str(value).replace("\\", "/") for value in plan.get("artifacts", [])} if isinstance(plan, dict) else set()
    recorded_artifacts = {str(item.get("workspace_path", "")).replace("\\", "/") for item in rebuilt if isinstance(item, dict)}
    if not planned_artifacts or recorded_artifacts != planned_artifacts:
        errors.append("rebuilt artifact set differs from build plan")
    for index, item in enumerate(rebuilt):
        try:
            artifact, relative = project_relative(project, item["path"], must_exist=True)
            if not relative.startswith(str(record.get("clean_directory", "")) + "/workspace/"):
                errors.append(f"rebuilt_files[{index}] is outside the clean workspace")
            if not artifact.is_file() or digest(artifact) != item.get("sha256"):
                errors.append(f"rebuilt file hash mismatch: {item.get('path')}")
        except (KeyError, OSError, ValueError) as exc:
            errors.append(f"rebuilt_files[{index}]: {exc}")
    if record.get("status") != "PASS":
        errors.append("clean build record is not PASS")
    status = "PASS" if not errors else "FAIL"
    emit({"status": status, "errors": errors, "run_id": record.get("run_id"), "manual_limit": "Consistency hashes detect stale or edited records but are not cryptographic third-party attestations."})
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
