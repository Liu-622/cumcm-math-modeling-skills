#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import emit, read_json


def require_fields(item: dict, fields: list[str], label: str, errors: list[str]) -> None:
    missing = [field for field in fields if field not in item]
    if missing:
        errors.append(f"{label} missing fields: {', '.join(missing)}")


def nonempty_list(item: dict, field: str, label: str, errors: list[str]) -> None:
    value = item.get(field)
    if not isinstance(value, list) or not value:
        errors.append(f"{label}.{field} must be a non-empty list")


def audit_p1(project: Path, errors: list[str]) -> set[str]:
    path = project / "evidence/problem_contracts.json"
    if not path.is_file():
        errors.append("missing evidence/problem_contracts.json")
        return set()
    data = read_json(path)
    questions = data.get("questions", [])
    fields = data.get("data_fields", [])
    if not questions:
        errors.append("P1 requires at least one question contract")
    if not fields:
        errors.append("P1 requires a non-empty data dictionary")
    ids: set[str] = set()
    for index, item in enumerate(questions):
        label = f"question[{index}]"
        require_fields(item, ["question_id", "task_verb", "requirements", "inputs", "outputs", "metrics", "constraints", "downstream_interfaces", "validation", "units_status", "time_direction", "result_template_mapping", "status"], label, errors)
        question_id = str(item.get("question_id", "")).strip()
        if not question_id or question_id in ids:
            errors.append(f"{label}: missing or duplicate question_id")
        ids.add(question_id)
        for field in ["inputs", "outputs", "metrics", "validation"]:
            nonempty_list(item, field, label, errors)
        requirements = item.get("requirements", [])
        if not isinstance(requirements, list) or not requirements:
            errors.append(f"{label}.requirements must be a non-empty list")
        else:
            explicit = False
            for req_index, requirement in enumerate(requirements):
                req_label = f"{label}.requirement[{req_index}]"
                if not isinstance(requirement, dict):
                    errors.append(f"{req_label} must be an object")
                    continue
                require_fields(requirement, ["type", "statement", "basis", "status"], req_label, errors)
                if requirement.get("type") not in {"EXPLICIT", "INFERRED"}:
                    errors.append(f"{req_label}: invalid type")
                explicit = explicit or requirement.get("type") == "EXPLICIT"
                if not str(requirement.get("statement", "")).strip() or not str(requirement.get("basis", "")).strip() or requirement.get("status") != "PASS":
                    errors.append(f"{req_label}: statement/basis must be non-empty and status must PASS")
            if not explicit:
                errors.append(f"{label}: at least one EXPLICIT requirement is required")
        for field in ["constraints", "downstream_interfaces"]:
            if not isinstance(item.get(field), list):
                errors.append(f"{label}.{field} must be a list")
        if item.get("units_status") != "PASS" or item.get("status") != "PASS":
            errors.append(f"{label}: units_status and status must PASS")
        for field in ["task_verb", "time_direction", "result_template_mapping"]:
            if not str(item.get(field, "")).strip():
                errors.append(f"{label}.{field} is empty")
    field_names: set[str] = set()
    for index, item in enumerate(fields):
        label = f"data_field[{index}]"
        required = ["field", "meaning", "unit", "object", "time_basis", "source", "source_type", "source_reference", "observed", "missing_policy", "status"]
        require_fields(item, required, label, errors)
        name = str(item.get("field", "")).strip()
        if not name or name in field_names:
            errors.append(f"{label}: missing or duplicate field")
        field_names.add(name)
        if item.get("status") != "PASS":
            errors.append(f"{label}: status must PASS")
        for field in ["meaning", "unit", "object", "time_basis", "source", "source_reference", "missing_policy"]:
            if not str(item.get(field, "")).strip():
                errors.append(f"{label}.{field} is empty; use an explicit N_A if needed")
        if item.get("source_type") not in {"PROVIDED", "EXTERNAL", "SYNTHETIC_SCENARIO"}:
            errors.append(f"{label}: invalid source_type")
        if not isinstance(item.get("observed"), bool):
            errors.append(f"{label}.observed must be boolean")
        if item.get("source_type") == "SYNTHETIC_SCENARIO" and item.get("observed") is not False:
            errors.append(f"{label}: synthetic scenario data cannot be marked observed")
    return ids


def audit_p2(project: Path, question_ids: set[str], errors: list[str]) -> None:
    path = project / "evidence/baselines.json"
    if not path.is_file():
        errors.append("missing evidence/baselines.json")
        return
    baselines = read_json(path).get("baselines", [])
    if not baselines:
        errors.append("P2 requires at least one baseline")
        return
    covered: set[str] = set()
    for index, item in enumerate(baselines):
        label = f"baseline[{index}]"
        required = ["question_id", "baseline_name", "method", "target_output", "failure_conditions", "current_data_evidence", "historical_review", "status"]
        require_fields(item, required, label, errors)
        qid = str(item.get("question_id", "")).strip()
        covered.add(qid)
        if qid not in question_ids:
            errors.append(f"{label}: unknown question_id {qid}")
        if item.get("status") != "PASS":
            errors.append(f"{label}: status must PASS")
        for field in ["failure_conditions", "current_data_evidence"]:
            nonempty_list(item, field, label, errors)
        review = item.get("historical_review")
        if not isinstance(review, dict) or review.get("searched") is not True:
            errors.append(f"{label}: historical_review.searched must be true")
            continue
        cases = review.get("cases", [])
        if not isinstance(cases, list):
            errors.append(f"{label}: historical_review.cases must be a list")
            continue
        if not cases and not str(review.get("no_transfer_reason", "")).strip():
            errors.append(f"{label}: explain why no historical case transfers")
        for case_index, case in enumerate(cases):
            case_label = f"{label}.case[{case_index}]"
            require_fields(case, ["case_id", "structural_similarity", "differences", "transferable", "prohibited_transfer", "status"], case_label, errors)
            if case.get("status") != "PASS":
                errors.append(f"{case_label}: status must PASS")
            for field in ["structural_similarity", "differences", "prohibited_transfer"]:
                if not str(case.get(field, "")).strip():
                    errors.append(f"{case_label}.{field} is empty")
    missing = sorted(question_ids - covered)
    if missing:
        errors.append(f"P2 lacks baselines for: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit P1/P2 semantic contracts.")
    parser.add_argument("project")
    parser.add_argument("--phase", choices=["P1", "P2"], required=True)
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors: list[str] = []
    try:
        question_ids = audit_p1(project, errors)
        if args.phase == "P2":
            audit_p2(project, question_ids, errors)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(str(exc))
    emit({"status": "PASS" if not errors else "FAIL", "phase": args.phase, "errors": errors, "manual_limit": "Semantic fields are structurally checked; their scientific truth still requires review."})
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
