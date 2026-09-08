#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import stat
from pathlib import Path

from common import PHASES, digest, emit, now, registry_defaults, write_json

MODES = {"training", "live", "赛前训练模式", "比赛实战模式"}


def copy_raw(source: Path, raw: Path) -> dict:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    target = raw / source.name
    if target.exists() and digest(target) != digest(source):
        index = 2
        # Preserve the complete original name, including extensionless dotfiles.
        while (raw / f"{source.name}.{index}").exists():
            index += 1
        target = raw / f"{source.name}.{index}"
    if not target.exists():
        shutil.copy2(source, target)
        try:
            target.chmod(target.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
        except OSError:
            pass
    return {
        "original_path": str(source),
        "raw_path": str(target.relative_to(raw.parent.parent)),
        "size_bytes": target.stat().st_size,
        "sha256": digest(target),
        "registered_at": now(),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize an evidence-gated CUMCM C project.")
    parser.add_argument("project")
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--source", action="append", default=[])
    args = parser.parse_args()
    mode = "training" if args.mode in {"training", "赛前训练模式"} else "live"
    project = Path(args.project).expanduser().resolve()
    manifest_path = project / "project_manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old.get("mode") != mode:
            raise SystemExit(f"mode is locked as {old.get('mode')}; refusing {mode}")
        raise SystemExit("project is already initialized; use gate.py <project> status or migrate")

    for rel in [
        "data/raw", "data/processed", "data/intermediate", "config", "code/io",
        "code/models", "code/solvers", "code/validation", "code/figures",
        "results/tables", "results/logs", "figures", "reports", "evidence",
        "paper", "support", "tests", "build/clean",
    ]:
        (project / rel).mkdir(parents=True, exist_ok=True)

    raw_entries = [copy_raw(Path(source), project / "data/raw") for source in args.source]
    created = now()
    manifest = {
        "schema_version": "2.0",
        "project_name": project.name,
        "created_at": created,
        "mode": mode,
        "mode_locked": True,
        "problem_family": "CUMCM-C",
        "raw_policy": "immutable raw files; transformations create new files",
        "raw_files": raw_entries,
        "rules_snapshot": "UNVERIFIED",
    }
    state = {
        "schema_version": "2.0",
        "current_phase": "P0",
        "updated_at": created,
        "phases": {
            phase: {
                "quality_status": "UNVERIFIED",
                "user_review": "NOT_SUBMITTED",
                "report": None,
                "evidence": [],
                "blockers": [],
            }
            for phase in PHASES
        },
        "history": [],
    }
    write_json(manifest_path, manifest)
    write_json(project / "workflow_state.json", state)
    for filename, payload in registry_defaults().items():
        path = project / "evidence" / filename
        if not path.exists():
            write_json(path, payload)
    write_json(project / "config/team_profile.json", {
        "schema_version": "1.0",
        "programming_languages": [],
        "hardware": "",
        "time_budget_hours": None,
        "priorities": [],
        "notes": "",
        "status": "OPTIONAL",
    })

    style_source = Path(__file__).resolve().parent.parent / "assets" / "visual-style"
    style_target = project / "support" / "visual-style"
    style_target.mkdir(parents=True, exist_ok=True)
    for source in style_source.iterdir():
        if source.is_file():
            shutil.copy2(source, style_target / source.name)

    (project / "plan.md").write_text(
        "# CUMCM C题证据驱动计划\n\n"
        f"- 模式：{mode}\n- 当前阶段：P0\n- 规则快照：UNVERIFIED\n"
        "- 原则：人工验收可豁免，数学、实验和复现硬门不可豁免。\n"
        "- 阶段：P0→P1→P2→P3→P4→P5→P6→P6R→P7→P8。\n",
        encoding="utf-8",
    )
    (project / "todo.md").write_text(
        "# 阶段待办\n\n" + "\n".join(f"- [ ] {phase}" for phase in PHASES) + "\n",
        encoding="utf-8",
    )
    emit({"status": "initialized", "schema_version": "2.0", "project": str(project), "mode": mode, "raw_files": len(raw_entries)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
