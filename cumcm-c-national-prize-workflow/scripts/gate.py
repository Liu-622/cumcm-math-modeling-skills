#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from common import PHASES, QUALITY, digest, emit, now, project_relative, registry_defaults, run_json_script, write_json


def load(project: Path) -> tuple[Path, dict]:
    path = project / "workflow_state.json"
    if not path.exists():
        raise SystemExit("workflow_state.json not found; run init_project.py first")
    return path, json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, state: dict) -> None:
    state["updated_at"] = now()
    write_json(path, state)


def latest_submitted_status(state: dict, phase: str) -> str | None:
    events = [event for event in state.get("history", []) if event.get("event") == "submitted" and event.get("phase") == phase]
    if not events:
        return None
    return events[-1].get("quality_status") or events[-1].get("status")


def migrate_state(state: dict) -> dict:
    if state.get("schema_version") == "2.0":
        return state
    migrated = dict(state)
    migrated["schema_version"] = "2.0"
    old_phases = state.get("phases", {})
    new_phases = {}
    for phase in PHASES:
        old = old_phases.get(phase, {})
        old_status = old.get("status", "UNVERIFIED")
        if old_status == "WAIVED":
            old_status = latest_submitted_status(state, phase) or "UNVERIFIED"
        if old_status not in QUALITY:
            old_status = "UNVERIFIED"
        old_review = old.get("review", "NOT_SUBMITTED")
        review_map = {"ACCEPTED": "ACCEPTED", "WAIVED": "WAIVED", "PENDING_USER": "PENDING_USER", "REJECTED": "REJECTED", "NOT_SUBMITTED": "NOT_SUBMITTED"}
        new_phases[phase] = {
            "quality_status": old_status,
            "user_review": review_map.get(old_review, "NOT_SUBMITTED"),
            "report": old.get("report"),
            "evidence": old.get("evidence", []),
            "blockers": old.get("blockers", []),
            "summary": old.get("summary", ""),
        }
    migrated["phases"] = new_phases
    migrated.setdefault("history", []).append({"event": "migrated_to_v2", "at": now()})
    first_blocked = next((phase for phase in PHASES if new_phases[phase]["quality_status"] != "PASS"), None)
    migrated["current_phase"] = first_blocked or "COMPLETE"
    return migrated


def migrate_project_files(project: Path) -> None:
    manifest_path = project / "project_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = "2.0"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evidence = project / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    for filename, payload in registry_defaults().items():
        path = evidence / filename
        if not path.exists():
            write_json(path, payload)
        else:
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            changed = False
            for key, value in payload.items():
                if key not in current:
                    current[key] = value
                    changed = True
            if changed:
                write_json(path, current)
    profile = project / "config/team_profile.json"
    if not profile.exists():
        write_json(profile, {"schema_version": "1.0", "programming_languages": [], "hardware": "", "time_budget_hours": None, "priorities": [], "notes": "", "status": "OPTIONAL"})
    style_source = Path(__file__).resolve().parent.parent / "assets" / "visual-style"
    style_target = project / "support" / "visual-style"
    style_target.mkdir(parents=True, exist_ok=True)
    for source in style_source.iterdir():
        if source.is_file() and not (style_target / source.name).exists():
            shutil.copy2(source, style_target / source.name)


def compact_status(state: dict) -> dict:
    if state.get("schema_version") != "2.0":
        return {"schema_version": state.get("schema_version", "1.0"), "migration_required": True, "current_phase": state.get("current_phase")}
    blockers = []
    for phase, record in state.get("phases", {}).items():
        if record.get("quality_status") != "PASS":
            blockers.append({"phase": phase, "quality_status": record.get("quality_status"), "blockers": record.get("blockers", [])})
    return {"schema_version": "2.0", "current_phase": state.get("current_phase"), "blockers": blockers, "phases": state.get("phases", {})}


def registry(project: Path, filename: str, key: str, errors: list[str]) -> list:
    path = project / "evidence" / filename
    if not path.is_file():
        errors.append(f"missing evidence registry: {filename}")
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON {filename}: {exc}")
        return []
    values = payload.get(key, [])
    if not isinstance(values, list):
        errors.append(f"{filename}: {key} must be a list")
        return []
    return values


def run_audit(project: Path, script: str, args: list[str], errors: list[str], project_last: bool = False, allow_partial: bool = True) -> None:
    command_args = [*args, str(project)] if project_last else [str(project), *args]
    returncode, payload = run_json_script(Path(__file__).with_name(script), command_args)
    accepted = {"PASS", "PARTIAL"} if allow_partial else {"PASS"}
    if returncode != 0 or payload.get("status") not in accepted:
        messages = payload.get("errors", [f"{script} failed"])
        errors.extend(f"{script}: {message}" for message in messages)


def check_format_audit(project: Path, errors: list[str]) -> None:
    path = project / "reports/CUMCM_FORMAT_AUDIT.json"
    if not path.is_file():
        errors.append("P8 requires reports/CUMCM_FORMAT_AUDIT.json")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid CUMCM_FORMAT_AUDIT.json: {exc}")
        return
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


def pass_preflight(project: Path, phase: str) -> list[str]:
    errors: list[str] = []
    if phase == "P0":
        manifest_path = project / "project_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        if manifest.get("rules_snapshot") in {None, "UNVERIFIED"}:
            errors.append("P0 requires a verified or explicitly frozen rules snapshot")
        if not manifest.get("raw_files"):
            errors.append("P0 requires at least one registered raw problem/data file")
    if phase == "P1":
        run_audit(project, "phase_contract_audit.py", ["--phase", "P1"], errors, allow_partial=False)
    if phase in {"P2", "P3", "P4", "P5", "P6", "P6R", "P7", "P8"}:
        run_audit(project, "phase_contract_audit.py", ["--phase", "P2"], errors, allow_partial=False)
    if phase in {"P3", "P4", "P5", "P6", "P6R", "P7", "P8"}:
        claims = registry(project, "claims.json", "claims", errors)
        experiments = registry(project, "experiments.json", "experiments", errors)
        if not claims:
            errors.append(f"{phase} requires a non-empty claims registry")
        if not experiments:
            errors.append(f"{phase} requires a non-empty experiments registry")
    if phase in {"P4", "P5", "P6", "P6R", "P7", "P8"}:
        contracts = registry(project, "model_contracts.json", "contracts", errors)
        if not contracts:
            errors.append(f"{phase} requires formula-code contracts")
        if phase == "P4":
            run_audit(project, "evidence_audit.py", [], errors)
    if phase in {"P5", "P6", "P6R", "P7", "P8"}:
        contracts = registry(project, "model_contracts.json", "contracts", errors)
        if any(item.get("status") != "PASS" for item in contracts):
            errors.append(f"{phase} requires every registered formula-code contract to PASS")
        optimizations = registry(project, "optimization_certificates.json", "certificates", errors)
        constraints = registry(project, "constraint_certificates.json", "certificates", errors)
        if not optimizations:
            errors.append(f"{phase} requires optimization certificates")
        if not constraints:
            errors.append(f"{phase} requires constraint certificates")
        run_audit(project, "evidence_audit.py", [], errors)
    if phase in {"P6", "P6R", "P7", "P8"}:
        experiments = registry(project, "experiments.json", "experiments", errors)
        sensitivities = registry(project, "sensitivity.json", "analyses", errors)
        if not any(item.get("role") == "FINAL_TEST" and item.get("status") == "PASS" for item in experiments):
            errors.append(f"{phase} requires a passed locked FINAL_TEST")
        if not sensitivities:
            errors.append(f"{phase} requires sensitivity evidence")
    if phase in {"P6R", "P7", "P8"}:
        red_path = project / "evidence/red_team.json"
        red = json.loads(red_path.read_text(encoding="utf-8")) if red_path.is_file() else {}
        provenance_ok = (
            red.get("generated_by") == "record_red_team.py"
            and red.get("reviewer_kind") in {"subagent", "external"}
            and red.get("producer_context_id")
            and red.get("reviewer_context_id")
            and red.get("producer_context_id") != red.get("reviewer_context_id")
        )
        if red.get("status") != "PASS" or not provenance_ok:
            errors.append(f"{phase} requires a passed red-team record with distinct reviewer provenance")
        run_audit(project, "evidence_audit.py", ["--strict"], errors)
    if phase in {"P7", "P8"}:
        run_audit(project, "figure_registry.py", ["audit"], errors, project_last=True)
        figures = registry(project, "figures.json", "figures", errors)
        if not figures:
            errors.append(f"{phase} requires a non-empty figure registry")
        if any(item.get("status") != "FINAL" for item in figures):
            errors.append(f"{phase} requires every paper figure to have status FINAL")
        paper = project / "paper"
        if not any(paper.rglob("*.pdf")):
            errors.append(f"{phase} requires a rendered paper PDF")
        if not (any(paper.rglob("*.tex")) or any(paper.rglob("*.typ")) or any(paper.rglob("*.docx"))):
            errors.append(f"{phase} requires paper source")
    if phase == "P8":
        run_audit(project, "clean_build_audit.py", [], errors)
        run_audit(project, "score_with_caps.py", [], errors, allow_partial=False)
        check_format_audit(project, errors)
        if not (project / "reports/P6R_RED_TEAM.md").is_file():
            errors.append("P8 requires reports/P6R_RED_TEAM.md")
    return list(dict.fromkeys(errors))


def advance(state: dict, phase: str) -> None:
    index = PHASES.index(phase)
    if phase == "P8":
        failed = [p for p in PHASES if state["phases"][p].get("quality_status") != "PASS"]
        if failed:
            raise SystemExit(f"cannot complete; non-PASS quality gates: {', '.join(failed)}")
        state["current_phase"] = "COMPLETE"
    else:
        state["current_phase"] = PHASES[index + 1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit and decide evidence-gated workflow stages.")
    parser.add_argument("project")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("migrate")

    submit = sub.add_parser("submit")
    submit.add_argument("--phase", choices=PHASES, required=True)
    submit.add_argument("--quality-status", choices=QUALITY)
    submit.add_argument("--status", choices=QUALITY, help="deprecated alias for --quality-status")
    submit.add_argument("--report", required=True)
    submit.add_argument("--summary", required=True)
    submit.add_argument("--evidence", action="append", default=[])
    submit.add_argument("--blocker", action="append", default=[])

    decide = sub.add_parser("decide")
    decide.add_argument("--phase", choices=PHASES, required=True)
    decide.add_argument("--decision", choices=["accept", "reject", "waive"], required=True)
    decide.add_argument("--note", default="")

    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    path, state = load(project)

    if args.command == "status":
        emit(compact_status(state))
        return 0
    if args.command == "migrate":
        if state.get("schema_version") == "2.0":
            migrate_project_files(project)
            emit({"status": "v2_resources_repaired", "current_phase": state.get("current_phase")})
            return 0
        state = migrate_state(state)
        migrate_project_files(project)
        save(path, state)
        emit({"status": "migrated", "current_phase": state["current_phase"]})
        return 0
    if state.get("schema_version") != "2.0":
        raise SystemExit("v1 workflow state; run gate.py <project> migrate first")

    phase = args.phase
    if state.get("current_phase") != phase:
        raise SystemExit(f"current phase is {state.get('current_phase')}; refusing operation on {phase}")
    record = state["phases"][phase]

    if args.command == "submit":
        quality = args.quality_status or args.status
        if quality is None:
            raise SystemExit("--quality-status is required")
        try:
            report, report_rel = project_relative(project, args.report, must_exist=True)
        except (ValueError, FileNotFoundError) as exc:
            raise SystemExit(f"invalid report path: {exc}") from exc
        if not report.is_file():
            raise SystemExit(f"report is not a file: {report}")
        invalid_evidence = []
        normalized_evidence = []
        for item in args.evidence:
            try:
                _, relative = project_relative(project, item, must_exist=True)
                normalized_evidence.append(relative)
            except (ValueError, FileNotFoundError):
                invalid_evidence.append(item)
        if invalid_evidence:
            raise SystemExit(f"invalid evidence path: {', '.join(invalid_evidence)}")
        if quality == "PASS" and args.blocker:
            raise SystemExit("PASS cannot contain blockers")
        if quality == "PASS":
            preflight_errors = pass_preflight(project, phase)
            if preflight_errors:
                emit({"phase": phase, "quality_status": "FAIL", "preflight_errors": preflight_errors})
                return 2
        record.update({
            "quality_status": quality,
            "user_review": "PENDING_USER",
            "report": report_rel,
            "summary": args.summary,
            "evidence": normalized_evidence,
            "blockers": args.blocker,
            "submitted_at": now(),
        })
        state["history"].append({"event": "submitted", "phase": phase, "quality_status": quality, "at": now()})
        save(path, state)
        emit({"phase": phase, "quality_status": quality, "user_review": "PENDING_USER", "current_phase": phase})
        return 0

    if record.get("user_review") != "PENDING_USER":
        raise SystemExit("phase has not been submitted for user review")
    if args.decision == "reject":
        record["user_review"] = "REJECTED"
        record["quality_status"] = "FAIL"
    elif args.decision == "accept":
        record["user_review"] = "ACCEPTED"
    else:
        record["user_review"] = "WAIVED"
    record["decision_note"] = args.note
    record["decided_at"] = now()
    state["history"].append({"event": args.decision, "phase": phase, "quality_status": record.get("quality_status"), "at": now(), "note": args.note})

    advanced = False
    if args.decision in {"accept", "waive"} and record.get("quality_status") == "PASS":
        advance(state, phase)
        advanced = True
    save(path, state)
    payload = {"phase": phase, "quality_status": record.get("quality_status"), "user_review": record.get("user_review"), "advanced": advanced, "current_phase": state.get("current_phase")}
    if args.decision in {"accept", "waive"} and not advanced:
        payload["reason"] = "human review cannot override a non-PASS quality gate"
        emit(payload)
        return 2
    emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
