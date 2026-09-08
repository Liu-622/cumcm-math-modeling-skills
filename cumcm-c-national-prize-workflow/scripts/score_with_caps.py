#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import NATIONAL_FIRST_THRESHOLD, emit, project_relative


def read(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply evidence-based hard caps to a CUMCM paper score.")
    parser.add_argument("project")
    parser.add_argument("--output", default="reports/FINAL_SCORE.json")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    evidence = project / "evidence"
    scoring = read(evidence / "scoring.json")
    contracts = read(evidence / "model_contracts.json").get("contracts", [])
    experiments = read(evidence / "experiments.json").get("experiments", [])
    optimizations = read(evidence / "optimization_certificates.json").get("certificates", [])
    claims = read(evidence / "claims.json").get("claims", [])
    red_team = read(evidence / "red_team.json")
    build = read(evidence / "build_verification.json")
    format_audit = read(project / "reports/CUMCM_FORMAT_AUDIT.json")

    dimensions = scoring.get("dimensions", [])
    if not dimensions:
        raise SystemExit("evidence/scoring.json has no dimensions")
    errors = []
    max_total = 0.0
    raw_total = 0.0
    adjusted = []
    inactive_innovation = any(
        claim.get("kind") == "innovation" and claim.get("disposition") == "INCLUDE" and claim.get("activation_status") != "PASS"
        for claim in claims
    )
    for index, dimension in enumerate(dimensions):
        name = str(dimension.get("name", f"dimension-{index}"))
        maximum = dimension.get("max_score")
        raw = dimension.get("raw_score")
        if not isinstance(maximum, (int, float)) or not isinstance(raw, (int, float)):
            errors.append(f"{name}: max_score and raw_score must be numeric")
            continue
        if maximum < 0 or raw < 0 or raw > maximum:
            errors.append(f"{name}: invalid score {raw}/{maximum}")
        if not str(dimension.get("reason", "")).strip():
            errors.append(f"{name}: scoring reason is required")
        effective = float(raw)
        reason = ""
        if inactive_innovation and ("创新" in name or "innovation" in name.lower()):
            effective = 0.0
            reason = "inactive innovation receives zero in the innovation dimension"
        max_total += float(maximum)
        raw_total += float(raw)
        adjusted.append({**dimension, "effective_score": effective, "adjustment_reason": reason})
    if abs(max_total - 100.0) > 1e-6:
        errors.append(f"dimension maximums sum to {max_total}, expected 100")
    if errors:
        emit({"status": "FAIL", "errors": errors})
        return 2

    adjusted_total = sum(item["effective_score"] for item in adjusted)
    caps = []
    if any(contract.get("status") == "FAIL" for contract in contracts):
        caps.append({"cap": 59, "reason": "core formula-code contract failed"})
    if any(
        experiment.get("role") == "FINAL_TEST"
        and (experiment.get("model_frozen_before_run") is not True or experiment.get("used_for_selection") is not False)
        for experiment in experiments
    ):
        caps.append({"cap": 69, "reason": "final-test leakage"})
    if any(experiment.get("comparison_id") and not experiment.get("paired_environment_id") for experiment in experiments):
        caps.append({"cap": 69, "reason": "strategy comparison lacks a common paired environment"})
    if any(
        certificate.get("core") is True
        and isinstance(certificate.get("relative_gap"), (int, float))
        and certificate["relative_gap"] > 0.20
        and not certificate.get("supplemental_bound_evidence")
        for certificate in optimizations
    ):
        caps.append({"cap": 79, "reason": "core optimization gap exceeds 20% without supplemental evidence"})
    open_serious = [
        issue for issue in red_team.get("issues", [])
        if issue.get("severity") in {"CRITICAL", "MAJOR"} and issue.get("status") != "CLOSED"
    ]
    provenance_ok = (
        red_team.get("generated_by") == "record_red_team.py"
        and red_team.get("reviewer_kind") in {"subagent", "external"}
        and red_team.get("producer_context_id")
        and red_team.get("reviewer_context_id")
        and red_team.get("producer_context_id") != red_team.get("reviewer_context_id")
    )
    if red_team.get("status") != "PASS" or not provenance_ok or open_serious:
        caps.append({"cap": 59, "reason": "independent red-team review is not passed"})
    if build.get("status") != "PASS" or build.get("generated_by") != "run_clean_build.py":
        caps.append({"cap": 79, "reason": "clean rebuild is not passed"})
    if format_audit.get("status") != "PASS" or any(
        item.get("level") == "FAIL" for item in format_audit.get("findings", [])
    ):
        caps.append({"cap": 59, "reason": "CUMCM official-format audit is not passed"})
    cap = min([item["cap"] for item in caps], default=100)
    final_score = min(adjusted_total, float(cap))
    if final_score >= 85:
        position = "国一候选竞争力；不构成获奖保证"
    elif final_score >= 80:
        position = "国二强竞争力，具备冲击国一可能"
    elif final_score >= 70:
        position = "国二候选，距稳定国一仍有明显证据缺口"
    elif final_score >= 60:
        position = "省级奖项竞争区，尚不具备国奖稳健性"
    else:
        position = "存在关键硬伤，不建议作为正式终稿"

    unverified = scoring.get("unverified_items", [])
    score_status = "PASS" if final_score >= NATIONAL_FIRST_THRESHOLD and not unverified else "PARTIAL"
    payload = {
        "status": score_status,
        "raw_score": raw_total,
        "adjusted_before_caps": adjusted_total,
        "hard_cap": cap,
        "final_score": final_score,
        "position": position,
        "dimensions": adjusted,
        "caps_applied": caps,
        "pass_threshold": NATIONAL_FIRST_THRESHOLD,
        "unverified_items": unverified,
    }
    try:
        output, _ = project_relative(project, args.output)
    except ValueError as exc:
        emit({"status": "FAIL", "errors": [str(exc)]})
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    output.write_text(text, encoding="utf-8")
    emit(payload)
    return 0 if score_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
