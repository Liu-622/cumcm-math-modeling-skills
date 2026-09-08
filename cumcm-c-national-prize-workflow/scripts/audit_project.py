#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import PHASES, digest, emit, project_relative, run_json_script


def load_json(path: Path, errors: list[str]) -> dict:
    if not path.is_file():
        errors.append(f"missing: {path.name}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON {path.name}: {exc}")
        return {}


def run_check(project: Path, script: str, args: list[str], errors: list[str]) -> dict:
    returncode, payload = run_json_script(Path(__file__).with_name(script), [str(project), *args])
    if returncode != 0 or payload.get("status") != "PASS":
        errors.extend(f"{script}: {message}" for message in payload.get("errors", ["failed"]))
    return payload


def check_format_audit(project: Path, errors: list[str]) -> dict:
    path = project / "reports/CUMCM_FORMAT_AUDIT.json"
    payload = load_json(path, errors)
    if not payload:
        return {}
    if payload.get("status") != "PASS":
        errors.append("CUMCM format audit status is not PASS")
    if any(item.get("level") == "FAIL" for item in payload.get("findings", [])):
        errors.append("CUMCM format audit contains FAIL findings")
    for field, hash_field, label in (
        ("pdf", "pdf_sha256", "paper PDF"),
        ("source", "source_sha256", "paper source"),
        ("support_archive", "support_archive_sha256", "support archive"),
    ):
        value = payload.get(field)
        expected = payload.get(hash_field)
        if not value:
            if field == "support_archive":
                continue
            errors.append(f"CUMCM format audit missing {field}")
            continue
        try:
            artifact, _ = project_relative(project, str(value), must_exist=True)
        except (ValueError, FileNotFoundError):
            errors.append(f"CUMCM format audit has invalid {label} path: {value}")
            continue
        if not artifact.is_file() or not expected or digest(artifact) != expected:
            errors.append(f"CUMCM format audit is stale for {label}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the single final audit for a CUMCM C project.")
    parser.add_argument("project")
    parser.add_argument("--output")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest = load_json(project / "project_manifest.json", errors)
    state = load_json(project / "workflow_state.json", errors)
    if manifest and manifest.get("schema_version") != "2.0":
        errors.append("project_manifest schema is not v2")
    for item in manifest.get("raw_files", []):
        try:
            path, _ = project_relative(project, str(item.get("raw_path", "")), must_exist=True)
            if not path.is_file() or digest(path) != item.get("sha256"):
                errors.append(f"raw file missing or changed: {item.get('raw_path')}")
        except (ValueError, FileNotFoundError):
            errors.append(f"raw path invalid: {item.get('raw_path')}")
    if manifest.get("rules_snapshot") in {None, "UNVERIFIED"}:
        errors.append("current-year rules snapshot is unverified")
    if state and state.get("schema_version") != "2.0":
        errors.append("workflow_state requires v2 migration")
    phases = state.get("phases", {})
    for phase in PHASES:
        record = phases.get(phase, {})
        if record.get("quality_status") != "PASS":
            errors.append(f"{phase} quality_status is not PASS")
        if record.get("user_review") not in {"ACCEPTED", "WAIVED"}:
            warnings.append(f"{phase} user_review is {record.get('user_review')}")
        report = record.get("report")
        if report:
            try:
                report_path, _ = project_relative(project, report, must_exist=True)
                if not report_path.is_file():
                    errors.append(f"{phase} report is not a file")
            except (ValueError, FileNotFoundError):
                errors.append(f"{phase} report path is invalid")
        for evidence_path in record.get("evidence", []):
            try:
                project_relative(project, evidence_path, must_exist=True)
            except (ValueError, FileNotFoundError):
                errors.append(f"{phase} evidence path is invalid: {evidence_path}")
    if state.get("current_phase") != "COMPLETE":
        errors.append(f"workflow is not COMPLETE: {state.get('current_phase')}")
    required = [
        "results/result_manifest.json", "reports/RESULTS_REPORT.md", "reports/P6_VALIDATION.md",
        "reports/P6R_RED_TEAM.md", "reports/VERIFY_REPORT.md", "reports/CUMCM_FORMAT_AUDIT.json",
    ]
    for rel in required:
        if not (project / rel).is_file():
            errors.append(f"missing final artifact: {rel}")
    phase_result = run_check(project, "phase_contract_audit.py", ["--phase", "P2"], errors)
    evidence_result = run_check(project, "evidence_audit.py", ["--strict"], errors)
    figure_code, figure_result = run_json_script(Path(__file__).with_name("figure_registry.py"), ["audit", str(project)])
    if figure_code != 0 or figure_result.get("status") != "PASS":
        errors.extend(f"figure_registry.py: {message}" for message in figure_result.get("errors", ["failed"]))
    build_result = run_check(project, "clean_build_audit.py", [], errors)
    score_result = run_check(project, "score_with_caps.py", [], errors)
    format_result = check_format_audit(project, errors)
    if not (project / "reports/FINAL_SCORE.json").is_file():
        errors.append("score report was not generated")
    paper_dir = project / "paper"
    if not any(paper_dir.rglob("*.pdf")):
        errors.append("no final paper PDF found under paper/")
    if not (any(paper_dir.rglob("*.tex")) or any(paper_dir.rglob("*.typ")) or any(paper_dir.rglob("*.docx"))):
        errors.append("no paper source found under paper/")
    payload = {
        "status": "FAIL" if errors else ("PARTIAL" if warnings else "PASS"),
        "errors": list(dict.fromkeys(errors)),
        "warnings": warnings,
        "checks": {"phase_contracts": phase_result, "evidence": evidence_result, "figures": figure_result, "clean_build": build_result, "score": score_result, "cumcm_format": format_result},
        "manual_limit": "These checks establish structural consistency and isolated reproducibility, not mathematical truth, originality, tamper resistance, or an award guarantee.",
    }
    if args.output:
        output, _ = project_relative(project, args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    emit(payload)
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
