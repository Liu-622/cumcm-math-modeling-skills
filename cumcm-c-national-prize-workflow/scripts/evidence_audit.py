#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import canonical_digest, digest, emit, project_relative

VALID_STATUS = {"PASS", "FAIL", "UNVERIFIED"}


def read_json(path: Path, errors: list[str]) -> dict:
    if not path.is_file():
        errors.append(f"missing registry: {path.name}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON {path.name}: {exc}")
        return {}


def present(item: dict, fields: list[str], label: str, errors: list[str]) -> None:
    missing = [field for field in fields if field not in item]
    if missing:
        errors.append(f"{label} missing fields: {', '.join(missing)}")


def existing_files(project: Path, files: object, label: str, errors: list[str]) -> None:
    if not isinstance(files, list) or not files:
        errors.append(f"{label}: evidence file list is empty")
        return
    for rel in files:
        try:
            candidate, _ = project_relative(project, str(rel), must_exist=True)
            if not candidate.is_file():
                errors.append(f"{label}: evidence is not a file: {rel}")
        except (ValueError, FileNotFoundError):
            errors.append(f"{label}: invalid project-relative file: {rel}")


def unique_map(items: list[dict], key: str, label: str, errors: list[str]) -> dict[str, dict]:
    result = {}
    for index, item in enumerate(items):
        value = item.get(key)
        if not value:
            errors.append(f"{label}[{index}] missing {key}")
        elif value in result:
            errors.append(f"duplicate {key}: {value}")
        else:
            result[str(value)] = item
    return result


def current_phase(project: Path) -> str | None:
    state_path = project / "workflow_state.json"
    if not state_path.is_file():
        return None
    try:
        phase = json.loads(state_path.read_text(encoding="utf-8")).get("current_phase")
    except json.JSONDecodeError:
        return None
    return phase


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit evidence contracts for a CUMCM C workflow.")
    parser.add_argument("project")
    parser.add_argument("--strict", action="store_true", help="require complete modeling evidence and a passed red-team review")
    parser.add_argument("--output")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    evidence = project / "evidence"
    errors: list[str] = []
    warnings: list[str] = []
    critical_flags: set[str] = set()
    phase = current_phase(project)
    strict = args.strict or phase in {"P6R", "P7", "P8", "COMPLETE"}
    final_stage = phase in {"P8", "COMPLETE"}
    ordered = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P6R", "P7", "P8", "COMPLETE"]

    def reached(target: str) -> bool:
        return args.strict or (phase in ordered and ordered.index(phase) >= ordered.index(target))

    claims_data = read_json(evidence / "claims.json", errors)
    contracts_data = read_json(evidence / "model_contracts.json", errors)
    processing_data = read_json(evidence / "data_processing.json", errors)
    experiments_data = read_json(evidence / "experiments.json", errors)
    optim_data = read_json(evidence / "optimization_certificates.json", errors)
    sensitivity_data = read_json(evidence / "sensitivity.json", errors)
    constraints_data = read_json(evidence / "constraint_certificates.json", errors)
    red_team = read_json(evidence / "red_team.json", errors)
    build_verification = read_json(evidence / "build_verification.json", errors)
    writing_data = read_json(evidence / "writing_audit.json", errors)

    for name, payload in [
        ("claims", claims_data), ("model_contracts", contracts_data), ("data_processing", processing_data),
        ("experiments", experiments_data), ("optimization_certificates", optim_data),
        ("sensitivity", sensitivity_data), ("constraint_certificates", constraints_data), ("writing_audit", writing_data),
    ]:
        if payload and payload.get("schema_version") != "2.0":
            errors.append(f"{name}: schema_version must be 2.0")

    contracts = contracts_data.get("contracts", [])
    assumptions = contracts_data.get("assumptions", [])
    symbols = contracts_data.get("symbols", [])
    processing = processing_data.get("decisions", [])
    experiments = experiments_data.get("experiments", [])
    validation_protocols = experiments_data.get("validation_protocols", [])
    optimizations = optim_data.get("certificates", [])
    claims = claims_data.get("claims", [])
    sensitivities = sensitivity_data.get("analyses", [])
    constraints = constraints_data.get("certificates", [])
    strengths = writing_data.get("strengths", [])
    limitations = writing_data.get("limitations", [])
    writing_checks = writing_data.get("consistency_checks", [])
    contract_map = unique_map(contracts, "formula_id", "contract", errors)
    experiment_map = unique_map(experiments, "experiment_id", "experiment", errors)
    optimization_map = unique_map(optimizations, "certificate_id", "optimization", errors)
    sensitivity_map = unique_map(sensitivities, "analysis_id", "sensitivity", errors)
    unique_map(claims, "claim_id", "claim", errors)

    if reached("P4") and (not assumptions or not symbols):
        errors.append("P4 requires non-empty assumptions and symbols")
    for index, item in enumerate(assumptions):
        label = f"assumption[{index}]"
        present(item, ["assumption_id", "statement", "basis", "model_impact", "failure_condition", "critical", "sensitivity_ids", "status"], label, errors)
        if item.get("status") not in VALID_STATUS:
            errors.append(f"{label}: invalid status")
        if item.get("status") == "PASS":
            for field in ["statement", "basis", "model_impact", "failure_condition"]:
                if not str(item.get(field, "")).strip():
                    errors.append(f"{label}.{field} is empty")
        if not isinstance(item.get("critical"), bool) or not isinstance(item.get("sensitivity_ids"), list):
            errors.append(f"{label}: critical must be boolean and sensitivity_ids must be a list")
        if reached("P6") and item.get("critical") is True:
            if not item.get("sensitivity_ids"):
                errors.append(f"{label}: critical assumption lacks sensitivity linkage")
            for sensitivity_id in item.get("sensitivity_ids", []):
                if sensitivity_id not in sensitivity_map or sensitivity_map[sensitivity_id].get("status") != "PASS":
                    errors.append(f"{label}: sensitivity is not PASS: {sensitivity_id}")
    symbol_ids: set[str] = set()
    for index, item in enumerate(symbols):
        label = f"symbol[{index}]"
        present(item, ["symbol", "meaning", "type", "unit", "domain", "code_name", "scope", "status"], label, errors)
        symbol = str(item.get("symbol", "")).strip()
        if not symbol or symbol in symbol_ids:
            errors.append(f"{label}: missing or duplicate symbol")
        symbol_ids.add(symbol)
        if item.get("status") != "PASS":
            errors.append(f"{label}: status must PASS")
        for field in ["meaning", "type", "unit", "domain", "code_name", "scope"]:
            if not str(item.get(field, "")).strip():
                errors.append(f"{label}.{field} is empty; use explicit N_A when needed")

    if reached("P5") and not processing:
        errors.append("P5 requires a non-empty data-processing decision log")
    for index, item in enumerate(processing):
        label = f"data_processing[{index}]"
        present(item, ["decision_id", "data_scope", "issue", "action", "rationale", "before_count", "after_count", "data_role", "evidence_files", "status"], label, errors)
        if item.get("action") not in {"KEEP", "IMPUTE", "REMOVE", "TRANSFORM", "FLAG"}:
            errors.append(f"{label}: invalid action")
        if item.get("data_role") not in {"OBSERVED", "DERIVED", "SYNTHETIC_SCENARIO"}:
            errors.append(f"{label}: invalid data_role")
        if item.get("data_role") == "SYNTHETIC_SCENARIO":
            if item.get("used_as_observed") is not False or not str(item.get("assumption_basis", "")).strip():
                errors.append(f"{label}: synthetic scenarios require used_as_observed=false and assumption_basis")
        before, after = item.get("before_count"), item.get("after_count")
        if not isinstance(before, int) or not isinstance(after, int) or before < 0 or after < 0:
            errors.append(f"{label}: before_count and after_count must be non-negative integers")
        if item.get("status") != "PASS":
            errors.append(f"{label}: status must PASS")
        else:
            existing_files(project, item.get("evidence_files"), label, errors)

    if reached("P6") and not validation_protocols:
        errors.append("P6 requires validation protocols selected by problem type")
    protocol_questions: set[str] = set()
    for index, item in enumerate(validation_protocols):
        label = f"validation_protocol[{index}]"
        present(item, ["protocol_id", "question_id", "problem_type", "metrics", "metric_selection_rationale", "design", "thresholds", "evidence_files", "status"], label, errors)
        protocol_questions.add(str(item.get("question_id", "")))
        if item.get("problem_type") not in {"PREDICTION", "CLASSIFICATION", "EVALUATION", "OPTIMIZATION", "MECHANISM", "SIMULATION", "OTHER"}:
            errors.append(f"{label}: invalid problem_type")
        if not isinstance(item.get("metrics"), list) or not item.get("metrics"):
            errors.append(f"{label}: metrics must be non-empty")
        if not isinstance(item.get("thresholds"), dict) or not item.get("thresholds"):
            errors.append(f"{label}: thresholds must be a non-empty object")
        for field in ["metric_selection_rationale", "design"]:
            if not str(item.get(field, "")).strip():
                errors.append(f"{label}.{field} is empty")
        if item.get("status") != "PASS":
            errors.append(f"{label}: status must PASS")
        else:
            existing_files(project, item.get("evidence_files"), label, errors)

    for formula_id, item in contract_map.items():
        label = f"contract {formula_id}"
        present(item, ["code_path", "test_path", "tested_invariants", "evidence_files", "status"], label, errors)
        if item.get("status") not in VALID_STATUS:
            errors.append(f"{label}: invalid status")
        if item.get("status") == "PASS":
            invariants = item.get("tested_invariants")
            if not isinstance(invariants, list) or not invariants:
                errors.append(f"{label}: no behavioral invariants")
            elif all("exist" in str(value).lower() or "存在" in str(value) for value in invariants):
                errors.append(f"{label}: existence-only checks are not behavioral tests")
            existing_files(project, [item.get("code_path"), item.get("test_path")], label, errors)
            existing_files(project, item.get("evidence_files"), label, errors)
        elif item.get("status") == "FAIL":
            critical_flags.add("FORMULA_CODE_MISMATCH")

    for experiment_id, item in experiment_map.items():
        label = f"experiment {experiment_id}"
        present(item, ["role", "purpose", "data_files", "seed", "sample_size", "model_frozen_before_run", "used_for_selection", "status"], label, errors)
        role = item.get("role")
        if role not in {"TRAIN", "VALIDATION", "FINAL_TEST", "STRESS"}:
            errors.append(f"{label}: invalid role {role}")
        if item.get("status") not in VALID_STATUS:
            errors.append(f"{label}: invalid status")
        if item.get("status") == "PASS":
            existing_files(project, item.get("data_files"), label, errors)
        if role == "FINAL_TEST" and item.get("status") == "PASS":
            if item.get("model_frozen_before_run") is not True or item.get("used_for_selection") is not False:
                errors.append(f"{label}: FINAL_TEST was not frozen or was used for selection")
                critical_flags.add("FINAL_TEST_LEAKAGE")
        if item.get("comparison_id") and not item.get("paired_environment_id"):
            errors.append(f"{label}: comparison lacks paired_environment_id")
            critical_flags.add("UNFAIR_COMPARISON")

    comparison_groups: dict[str, list[dict]] = {}
    for item in experiments:
        if item.get("comparison_id"):
            comparison_groups.setdefault(str(item["comparison_id"]), []).append(item)
    for comparison_id, group in comparison_groups.items():
        environments = {item.get("paired_environment_id") for item in group}
        embedded_plans = set()
        for item in group:
            embedded_plans.update(str(value) for value in item.get("compared_plans", []))
        if len(environments) > 1:
            errors.append(f"comparison {comparison_id}: experiments use different paired environments")
            critical_flags.add("UNFAIR_COMPARISON")
        if len(group) < 2 and len(embedded_plans) < 2:
            errors.append(f"comparison {comparison_id}: fewer than two compared plans are registered")
            critical_flags.add("UNFAIR_COMPARISON")

    for certificate_id, item in optimization_map.items():
        label = f"optimization {certificate_id}"
        present(item, ["question", "core", "incumbent", "best_bound", "sense", "absolute_gap", "relative_gap", "runtime_seconds", "termination", "solver", "structure_scope", "allowed_language", "status"], label, errors)
        if item.get("status") not in VALID_STATUS:
            errors.append(f"{label}: invalid status")
        gap = item.get("relative_gap")
        if item.get("core") is True and isinstance(gap, (int, float)) and gap > 0.20:
            supplements = item.get("supplemental_bound_evidence", [])
            if not supplements:
                errors.append(f"{label}: core relative gap exceeds 20% without supplemental bound evidence")
                critical_flags.add("CORE_GAP_OVER_20_PERCENT")
            else:
                existing_files(project, supplements, label, errors)

    for index, item in enumerate(sensitivities):
        label = f"sensitivity[{index}]"
        present(item, ["analysis_id", "target", "perturbation_type", "decision_policy", "mean_preserving", "range", "sample_size", "seed", "evidence_files", "status"], label, errors)
        if item.get("decision_policy") not in {"FIXED_PLAN", "REOPTIMIZED"}:
            errors.append(f"{label}: invalid decision_policy")
        if item.get("status") not in VALID_STATUS:
            errors.append(f"{label}: invalid status")
        if item.get("perturbation_type") == "variance" and item.get("mean_preserving") is not True:
            errors.append(f"{label}: variance stress is not mean preserving")
            critical_flags.add("INVALID_SENSITIVITY")
        if item.get("status") == "PASS":
            existing_files(project, item.get("evidence_files"), label, errors)

    for index, item in enumerate(constraints):
        label = f"constraint[{index}]"
        present(item, ["plan_id", "constraint_id", "applicability", "status", "max_violation", "tolerance", "evidence_file"], label, errors)
        applicable = item.get("applicability")
        status = item.get("status")
        if status not in VALID_STATUS | {"N_A"}:
            errors.append(f"{label}: invalid status")
        if applicable is False and (status != "N_A" or item.get("max_violation") is not None):
            errors.append(f"{label}: non-applicable constraint must be N_A with null violation")
        if applicable is True and status == "N_A":
            errors.append(f"{label}: applicable constraint cannot be N_A")
        if status == "PASS":
            existing_files(project, [item.get("evidence_file")], label, errors)

    for index, item in enumerate(claims):
        claim_id = item.get("claim_id", index)
        label = f"claim {claim_id}"
        present(item, ["question", "kind", "disposition", "wording", "allowed_language", "forbidden_language", "formula_ids", "evidence_files", "experiment_ids", "falsifier", "status"], label, errors)
        if item.get("disposition") not in {"INCLUDE", "EXCLUDE"}:
            errors.append(f"{label}: invalid disposition")
        if item.get("status") not in VALID_STATUS:
            errors.append(f"{label}: invalid status")
        if item.get("status") != "PASS" or item.get("disposition") == "EXCLUDE":
            continue
        if not str(item.get("falsifier", "")).strip():
            errors.append(f"{label}: falsifier is empty")
        existing_files(project, item.get("evidence_files"), label, errors)
        for formula_id in item.get("formula_ids", []):
            if formula_id not in contract_map or contract_map[formula_id].get("status") != "PASS":
                errors.append(f"{label}: formula contract not PASS: {formula_id}")
        for experiment_id in item.get("experiment_ids", []):
            if experiment_id not in experiment_map or experiment_map[experiment_id].get("status") != "PASS":
                errors.append(f"{label}: experiment not PASS: {experiment_id}")
        if item.get("kind") == "innovation" and item.get("activation_status") != "PASS":
            errors.append(f"{label}: innovation is not activated")
            critical_flags.add("INACTIVE_INNOVATION")
        if item.get("kind") == "optimality":
            ids = item.get("certificate_ids", [])
            if not ids:
                errors.append(f"{label}: optimality claim lacks certificate_ids")
            for certificate_id in ids:
                if certificate_id not in optimization_map or optimization_map[certificate_id].get("status") != "PASS":
                    errors.append(f"{label}: optimization certificate not PASS: {certificate_id}")

    if reached("P6"):
        claim_questions = {str(item.get("question", "")) for item in claims if item.get("disposition") == "INCLUDE"}
        missing_protocols = sorted(claim_questions - protocol_questions)
        if missing_protocols:
            errors.append(f"validation protocols do not cover included-claim questions: {', '.join(missing_protocols)}")

    if reached("P7") and (not strengths or not limitations or not writing_checks):
        errors.append("P7 requires evidence-backed strengths, limitations, and consistency checks")
    for kind, values in [("strength", strengths), ("limitation", limitations)]:
        for index, item in enumerate(values):
            label = f"{kind}[{index}]"
            fields = ["statement", "evidence_files", "status"] + (["boundary"] if kind == "limitation" else [])
            present(item, fields, label, errors)
            if not str(item.get("statement", "")).strip() or (kind == "limitation" and not str(item.get("boundary", "")).strip()):
                errors.append(f"{label}: statement/boundary is empty")
            if item.get("status") != "PASS":
                errors.append(f"{label}: status must PASS")
            else:
                existing_files(project, item.get("evidence_files"), label, errors)
    required_checks = {"TERMS", "SYMBOLS", "SECTION_PROMISES", "NUMBERS", "PAGE_BUDGET", "PADDING"}
    observed_checks: set[str] = set()
    for index, item in enumerate(writing_checks):
        label = f"writing_check[{index}]"
        present(item, ["check", "evidence_files", "status"], label, errors)
        check = str(item.get("check", ""))
        observed_checks.add(check)
        if check not in required_checks | {"REFERENCES", "FORMAT"}:
            errors.append(f"{label}: invalid check")
        if item.get("status") != "PASS":
            errors.append(f"{label}: status must PASS")
        else:
            existing_files(project, item.get("evidence_files"), label, errors)
    if reached("P7") and required_checks - observed_checks:
        errors.append(f"writing audit missing checks: {', '.join(sorted(required_checks - observed_checks))}")

    issues = red_team.get("issues", []) if isinstance(red_team, dict) else []
    open_serious = [issue for issue in issues if issue.get("severity") in {"CRITICAL", "MAJOR"} and issue.get("status") != "CLOSED"]
    if open_serious:
        errors.append(f"red team has {len(open_serious)} open CRITICAL/MAJOR issues")
        critical_flags.add("OPEN_RED_TEAM_ISSUES")
    if strict:
        provenance_ok = (
            red_team.get("generated_by") == "record_red_team.py"
            and red_team.get("reviewer_kind") in {"subagent", "external"}
            and red_team.get("producer_context_id")
            and red_team.get("reviewer_context_id")
            and red_team.get("producer_context_id") != red_team.get("reviewer_context_id")
        )
        if red_team.get("status") != "PASS" or not provenance_ok:
            errors.append("strict audit requires a passed red-team record with distinct reviewer provenance")
        unsigned = {key: value for key, value in red_team.items() if key != "record_hash"}
        if red_team.get("record_hash") != canonical_digest(unsigned):
            errors.append("red-team record consistency hash mismatch")
        try:
            report, _ = project_relative(project, str(red_team.get("report_path", "")), must_exist=True)
            if not report.is_file() or digest(report) != red_team.get("report_sha256"):
                errors.append("red-team report hash mismatch")
        except (ValueError, FileNotFoundError):
            errors.append("red-team report path is invalid")
        for item in red_team.get("input_files", []):
            try:
                source, _ = project_relative(project, str(item.get("path", "")), must_exist=True)
                if not source.is_file() or digest(source) != item.get("sha256"):
                    errors.append(f"red-team input hash mismatch: {item.get('path')}")
            except (ValueError, FileNotFoundError):
                errors.append(f"red-team input path is invalid: {item.get('path')}")
        if final_stage and build_verification.get("status") != "PASS":
            errors.append("strict audit requires build_verification.status=PASS")
            critical_flags.add("CLEAN_BUILD_FAILED")
        for name, values in [
            ("claims", claims), ("model contracts", contracts), ("experiments", experiments),
            ("optimization certificates", optimizations), ("sensitivity analyses", sensitivities),
            ("constraint certificates", constraints), ("assumptions", assumptions), ("symbols", symbols),
            ("data-processing decisions", processing), ("validation protocols", validation_protocols),
            ("writing strengths", strengths), ("writing limitations", limitations), ("writing checks", writing_checks),
        ]:
            if not values:
                errors.append(f"strict audit requires non-empty {name}")
        included_claims = [item for item in claims if item.get("disposition") == "INCLUDE"]
        if not included_claims:
            errors.append("strict audit requires at least one included claim")
        for item in included_claims:
            if item.get("status") != "PASS":
                errors.append(f"strict audit: included claim is not PASS: {item.get('claim_id')}")
        for name, values in [
            ("model contract", contracts), ("experiment", experiments),
            ("optimization certificate", optimizations), ("sensitivity analysis", sensitivities),
        ]:
            for item in values:
                if item.get("status") != "PASS":
                    errors.append(f"strict audit: {name} is not PASS")
        for item in constraints:
            if item.get("status") not in {"PASS", "N_A"}:
                errors.append("strict audit: constraint certificate is unresolved")
    else:
        for name, values in [("claims", claims), ("model contracts", contracts), ("experiments", experiments)]:
            if not values:
                warnings.append(f"not populated yet: {name}")

    status = "FAIL" if errors else ("PARTIAL" if warnings else "PASS")
    payload = {
        "status": status,
        "strict": strict,
        "final_stage": final_stage,
        "counts": {
            "claims": len(claims), "model_contracts": len(contracts), "experiments": len(experiments),
            "optimization_certificates": len(optimizations), "sensitivity_analyses": len(sensitivities),
            "constraint_certificates": len(constraints), "assumptions": len(assumptions), "symbols": len(symbols),
            "data_processing": len(processing), "validation_protocols": len(validation_protocols),
            "writing_checks": len(writing_checks),
        },
        "critical_flags": sorted(critical_flags),
        "errors": errors,
        "warnings": warnings,
        "manual_limit": "Structural evidence checks do not prove mathematical correctness; P6R remains mandatory.",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        try:
            output, _ = project_relative(project, args.output)
        except ValueError as exc:
            emit({"status": "FAIL", "errors": [str(exc)]})
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    emit(payload)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
