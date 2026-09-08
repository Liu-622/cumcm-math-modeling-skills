#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "2.0"
PHASES = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P6R", "P7", "P8"]
QUALITY = ["PASS", "PARTIAL", "FAIL", "UNVERIFIED"]
REVIEWS = ["ACCEPTED", "WAIVED", "PENDING_USER", "NOT_SUBMITTED", "REJECTED"]
NATIONAL_FIRST_THRESHOLD = 85.0

_DEFAULTS = {
    "problem_contracts.json": {"schema_version": SCHEMA_VERSION, "questions": [], "data_fields": []},
    "baselines.json": {"schema_version": SCHEMA_VERSION, "baselines": []},
    "claims.json": {"schema_version": SCHEMA_VERSION, "claims": []},
    "model_contracts.json": {"schema_version": SCHEMA_VERSION, "contracts": [], "assumptions": [], "symbols": []},
    "data_processing.json": {"schema_version": SCHEMA_VERSION, "decisions": []},
    "experiments.json": {"schema_version": SCHEMA_VERSION, "experiments": [], "validation_protocols": []},
    "optimization_certificates.json": {"schema_version": SCHEMA_VERSION, "certificates": []},
    "sensitivity.json": {"schema_version": SCHEMA_VERSION, "analyses": []},
    "constraint_certificates.json": {"schema_version": SCHEMA_VERSION, "certificates": []},
    "red_team.json": {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "record_red_team.py",
        "reviewer_kind": "",
        "producer_context_id": "",
        "reviewer_context_id": "",
        "report_path": "",
        "report_sha256": "",
        "input_files": [],
        "issues": [],
        "status": "UNVERIFIED",
    },
    "build_plan.json": {
        "schema_version": SCHEMA_VERSION,
        "copy_paths": [],
        "steps": [],
        "artifacts": [],
    },
    "build_verification.json": {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "run_clean_build.py",
        "run_id": "",
        "plan_sha256": "",
        "clean_directory": "",
        "source_snapshot": [],
        "commands": [],
        "dependencies": {},
        "compile_log": "",
        "compile_log_sha256": "",
        "rebuilt_files": [],
        "status": "UNVERIFIED",
    },
    "scoring.json": {"schema_version": SCHEMA_VERSION, "dimensions": [
        {"name": "审题与数据口径", "max_score": 15, "raw_score": 0, "reason": ""},
        {"name": "模型正确性", "max_score": 25, "raw_score": 0, "reason": ""},
        {"name": "算法与可复现性", "max_score": 20, "raw_score": 0, "reason": ""},
        {"name": "验证与稳健性", "max_score": 15, "raw_score": 0, "reason": ""},
        {"name": "创新性", "max_score": 15, "raw_score": 0, "reason": ""},
        {"name": "写作与可视化", "max_score": 10, "raw_score": 0, "reason": ""},
    ], "unverified_items": []},
    "figures.json": {"schema_version": SCHEMA_VERSION, "figures": []},
    "writing_audit.json": {"schema_version": SCHEMA_VERSION, "strengths": [], "limitations": [], "consistency_checks": []},
}


def registry_defaults() -> dict[str, object]:
    return copy.deepcopy(_DEFAULTS)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit(value: object) -> None:
    # Machine-readable stdout stays ASCII, so GBK/UTF-8 console defaults cannot corrupt it.
    print(json.dumps(value, ensure_ascii=True, indent=2))


def project_relative(project: Path, value: str | Path, *, must_exist: bool = False) -> tuple[Path, str]:
    raw = Path(value)
    candidate = raw.resolve() if raw.is_absolute() else (project / raw).resolve()
    try:
        relative = candidate.relative_to(project.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {value}") from exc
    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate, relative.as_posix()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_json_script(script: Path, args: list[str]) -> tuple[int, dict]:
    env = os.environ.copy()
    env.pop("PYTHONUTF8", None)
    env.pop("PYTHONIOENCODING", None)
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"status": "FAIL", "errors": [f"{script.name} returned invalid JSON"], "stderr": proc.stderr[-1000:]}
    return proc.returncode, payload
