#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import SCHEMA_VERSION, canonical_digest, digest, emit, now, project_relative, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a traceable red-team record from an independent review artifact.")
    parser.add_argument("project")
    parser.add_argument("--reviewer-kind", choices=["subagent", "external"], required=True)
    parser.add_argument("--producer-context", required=True)
    parser.add_argument("--reviewer-context", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--input", action="append", default=[], required=True)
    parser.add_argument("--issues-json", help="JSON file containing an issues list")
    parser.add_argument("--verdict", choices=["PASS", "FAIL", "UNVERIFIED"], required=True)
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors: list[str] = []
    if args.producer_context.strip() == args.reviewer_context.strip():
        errors.append("producer and reviewer context IDs must differ")
    try:
        report, report_rel = project_relative(project, args.report, must_exist=True)
    except (ValueError, FileNotFoundError) as exc:
        errors.append(str(exc))
        report, report_rel = project, ""
    inputs = []
    for raw in args.input:
        try:
            candidate, relative = project_relative(project, raw, must_exist=True)
            if not candidate.is_file():
                raise ValueError(f"red-team input is not a file: {raw}")
            inputs.append({"path": relative, "sha256": digest(candidate)})
        except (ValueError, FileNotFoundError) as exc:
            errors.append(str(exc))
    issues = []
    if args.issues_json:
        try:
            issue_path, _ = project_relative(project, args.issues_json, must_exist=True)
            payload = json.loads(issue_path.read_text(encoding="utf-8"))
            issues = payload.get("issues", payload) if isinstance(payload, dict) else payload
            if not isinstance(issues, list):
                raise ValueError("issues JSON must be a list or contain an issues list")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
    for index, issue in enumerate(issues):
        if not isinstance(issue, dict):
            errors.append(f"issue[{index}] must be an object")
            continue
        missing = [field for field in ["issue_id", "severity", "status", "reproduction", "evidence", "impact", "rollback_phase", "closure_evidence"] if field not in issue]
        if missing:
            errors.append(f"issue[{index}] missing: {', '.join(missing)}")
        if issue.get("severity") not in {"CRITICAL", "MAJOR", "MINOR"}:
            errors.append(f"issue[{index}] invalid severity")
        if issue.get("status") not in {"OPEN", "CLOSED"}:
            errors.append(f"issue[{index}] invalid status")
    open_serious = [issue for issue in issues if isinstance(issue, dict) and issue.get("severity") in {"CRITICAL", "MAJOR"} and issue.get("status") != "CLOSED"]
    if args.verdict == "PASS" and open_serious:
        errors.append("PASS is impossible with open CRITICAL/MAJOR issues")
    if errors:
        emit({"status": "FAIL", "errors": errors})
        return 2
    record = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "record_red_team.py",
        "recorded_at": now(),
        "reviewer_kind": args.reviewer_kind,
        "producer_context_id": args.producer_context.strip(),
        "reviewer_context_id": args.reviewer_context.strip(),
        "report_path": report_rel,
        "report_sha256": digest(report),
        "input_files": inputs,
        "issues": issues,
        "status": args.verdict,
    }
    record["record_hash"] = canonical_digest(record)
    write_json(project / "evidence/red_team.json", record)
    emit(record)
    return 0 if args.verdict == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
