#!/usr/bin/env python3
"""Regression tests for executable workflow guarantees."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from common import digest
from gate import migrate_state

HERE = Path(__file__).resolve().parent


def run(script: str, *args: str, expected: int = 0) -> dict:
    env = os.environ.copy()
    env.pop("PYTHONUTF8", None)
    env.pop("PYTHONIOENCODING", None)
    result = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, encoding="utf-8", env=env)
    if result.returncode != expected:
        raise AssertionError(f"{script} returned {result.returncode}, expected {expected}\n{result.stdout}\n{result.stderr}")
    if not result.stdout.strip() and expected != 0:
        return {"status": "REJECTED", "stderr": result.stderr}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{script} emitted invalid JSON: {result.stdout!r}") from exc


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def score(project: Path, raw_score: int, expected: int) -> dict:
    write(project / "evidence/scoring.json", {"schema_version": "2.0", "dimensions": [{"name": "总分", "max_score": 100, "raw_score": raw_score, "reason": "fixture"}], "unverified_items": []})
    return run("score_with_caps.py", str(project), expected=expected)


def main() -> int:
    passed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="cumcm-c-workflow-") as temp:
        root = Path(temp)
        source_a = root / "a" / ".gitignore"
        source_b = root / "b" / ".gitignore"
        source_a.parent.mkdir(); source_b.parent.mkdir()
        source_a.write_text("a", encoding="utf-8"); source_b.write_text("b", encoding="utf-8")
        project = root / "project"
        initialized = run("init_project.py", str(project), "--mode", "training", "--source", str(source_a), "--source", str(source_b))
        assert initialized["status"] == "initialized"
        assert (project / "data/raw/.gitignore").is_file() and (project / "data/raw/.gitignore.2").is_file()
        assert (project / "support/visual-style/palette.json").is_file()
        passed += ["default Windows-safe JSON", "raw collision naming", "style asset activation"]

        manifest_path = project / "project_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")); manifest["rules_snapshot"] = "fixture"; write(manifest_path, manifest)
        run("gate.py", str(project), "submit", "--phase", "P0", "--quality-status", "PASS", "--report", "plan.md", "--summary", "fixture")
        run("gate.py", str(project), "decide", "--phase", "P0", "--decision", "waive")
        run("gate.py", str(project), "submit", "--phase", "P1", "--quality-status", "PARTIAL", "--report", "plan.md", "--summary", "fixture", "--blocker", "intentional")
        run("gate.py", str(project), "decide", "--phase", "P1", "--decision", "waive", expected=2)
        assert json.loads((project / "workflow_state.json").read_text(encoding="utf-8"))["current_phase"] == "P1"
        passed.append("waiver cannot bypass quality")

        semantic = root / "semantic"
        problem = root / "problem.txt"; problem.write_text("problem", encoding="utf-8")
        run("init_project.py", str(semantic), "--mode", "training", "--source", str(problem))
        manifest_path = semantic / "project_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")); manifest["rules_snapshot"] = "fixture"; write(manifest_path, manifest)
        run("gate.py", str(semantic), "submit", "--phase", "P0", "--quality-status", "PASS", "--report", "plan.md", "--summary", "fixture")
        run("gate.py", str(semantic), "decide", "--phase", "P0", "--decision", "waive")
        empty_p1 = run("gate.py", str(semantic), "submit", "--phase", "P1", "--quality-status", "PASS", "--report", "plan.md", "--summary", "fixture", expected=2)
        assert empty_p1["quality_status"] == "FAIL"
        write(semantic / "evidence/problem_contracts.json", {"schema_version": "2.0", "questions": [{"question_id": "Q1", "task_verb": "predict", "requirements": [{"type": "EXPLICIT", "statement": "predict y", "basis": "problem statement", "status": "PASS"}], "inputs": ["x"], "outputs": ["y"], "metrics": ["MAE"], "constraints": [], "downstream_interfaces": [], "validation": ["holdout"], "units_status": "PASS", "time_direction": "past to future", "result_template_mapping": "result.xlsx", "status": "PASS"}], "data_fields": [{"field": "x", "meaning": "input", "unit": "1", "object": "sample", "time_basis": "day", "source": "attachment", "source_type": "PROVIDED", "source_reference": "problem.txt", "observed": True, "missing_policy": "reject", "status": "PASS"}]})
        run("gate.py", str(semantic), "submit", "--phase", "P1", "--quality-status", "PASS", "--report", "plan.md", "--summary", "fixture")
        run("gate.py", str(semantic), "decide", "--phase", "P1", "--decision", "waive")
        p1_path = semantic / "evidence/problem_contracts.json"
        p1_payload = json.loads(p1_path.read_text(encoding="utf-8"))
        p1_payload["data_fields"][0].update({"source_type": "SYNTHETIC_SCENARIO", "observed": True})
        write(p1_path, p1_payload)
        synthetic = run("phase_contract_audit.py", str(semantic), "--phase", "P1", expected=2)
        assert any("synthetic scenario" in value for value in synthetic["errors"])
        p1_payload["data_fields"][0].update({"source_type": "PROVIDED", "observed": True})
        write(p1_path, p1_payload)
        run("gate.py", str(semantic), "submit", "--phase", "P2", "--quality-status", "PASS", "--report", "plan.md", "--summary", "fixture", expected=2)
        write(semantic / "evidence/baselines.json", {"schema_version": "2.0", "baselines": [{"question_id": "Q1", "baseline_name": "mean", "method": "training mean", "target_output": "y", "failure_conditions": ["trend"], "current_data_evidence": ["distribution checked"], "historical_review": {"searched": True, "cases": [], "no_transfer_reason": "no structurally comparable case"}, "status": "PASS"}]})
        run("gate.py", str(semantic), "submit", "--phase", "P2", "--quality-status", "PASS", "--report", "plan.md", "--summary", "fixture")
        run("gate.py", str(semantic), "decide", "--phase", "P2", "--decision", "waive")
        run("gate.py", str(semantic), "submit", "--phase", "P3", "--quality-status", "PASS", "--report", "plan.md", "--summary", "fixture", expected=2)
        outside = root / "outside.md"; outside.write_text("outside", encoding="utf-8")
        run("gate.py", str(semantic), "submit", "--phase", "P3", "--quality-status", "PARTIAL", "--report", str(outside), "--summary", "fixture", expected=1)
        passed += ["P1 semantic gate", "synthetic-data role gate", "P2 baseline gate", "project-relative paths"]

        write(project / "evidence/claims.json", {"schema_version": "2.0", "claims": [{"claim_id": "X", "question": "Q1", "kind": "innovation", "disposition": "EXCLUDE", "wording": "rejected candidate", "allowed_language": [], "forbidden_language": [], "formula_ids": [], "evidence_files": [], "experiment_ids": [], "activation_status": "FAIL", "falsifier": "failed activation", "status": "PASS"}]})
        excluded = run("evidence_audit.py", str(project))
        assert "INACTIVE_INNOVATION" not in excluded["critical_flags"]
        passed.append("excluded innovation semantics")

        old = {"schema_version": "1.0", "phases": {"P0": {"status": "WAIVED", "review": "WAIVED"}}, "history": [{"event": "submitted", "phase": "P0", "status": "PASS"}]}
        assert migrate_state(old)["phases"]["P0"]["quality_status"] == "PASS"
        passed.append("v1 migration")

        build = root / "build-project"
        run("init_project.py", str(build), "--mode", "training", "--source", str(problem))
        task = build / "code/build_task.py"
        task.write_text("from pathlib import Path\nPath('results').mkdir(exist_ok=True)\nPath('paper').mkdir(exist_ok=True)\nPath('results/core.txt').write_text('42', encoding='utf-8')\nPath('paper/final.pdf').write_bytes(b'%PDF-1.4\\n%%EOF\\n')\n", encoding="utf-8")
        write(build / "evidence/build_plan.json", {"schema_version": "2.0", "copy_paths": ["code/build_task.py"], "steps": [{"argv": ["{python}", "code/build_task.py"], "cwd": ".", "timeout_seconds": 60}], "artifacts": ["results/core.txt", "paper/final.pdf"]})
        built = run("run_clean_build.py", str(build)); assert built["status"] == "PASS"
        assert run("clean_build_audit.py", str(build))["status"] == "PASS"
        report = build / "reports/P6R_RED_TEAM.md"; report.write_text("# independent review\n", encoding="utf-8")
        run("record_red_team.py", str(build), "--reviewer-kind", "subagent", "--producer-context", "same", "--reviewer-context", "same", "--report", "reports/P6R_RED_TEAM.md", "--input", "code/build_task.py", "--verdict", "PASS", expected=2)
        run("record_red_team.py", str(build), "--reviewer-kind", "subagent", "--producer-context", "producer-1", "--reviewer-context", "reviewer-2", "--report", "reports/P6R_RED_TEAM.md", "--input", "code/build_task.py", "--verdict", "PASS")
        write(build / "reports/CUMCM_FORMAT_AUDIT.json", {"status": "PASS", "findings": []})
        assert score(build, 84, 2)["status"] == "PARTIAL"
        assert score(build, 85, 0)["status"] == "PASS"

        for rel, content in {
            "code/model.py": "def identity(x): return x\n",
            "tests/test_contract.py": "assert True\n",
            "results/evidence.csv": "value\n1\n",
            "results/result_manifest.json": "{}\n",
            "figures/fig.pdf": "%PDF-1.4\n%%EOF\n",
            "paper/main.tex": "\\documentclass{article}\\begin{document}ok\\end{document}\n",
            "paper/final.pdf": "%PDF-1.4\n%%EOF\n",
            "reports/RESULTS_REPORT.md": "# Results\n",
            "reports/P6_VALIDATION.md": "# Validation\n",
            "reports/VERIFY_REPORT.md": "# Verify\n",
        }.items():
            target = build / rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(content, encoding="utf-8")
        figure_script = build / "code/figure.py"
        figure_script.write_text("from pathlib import Path\nimport json, matplotlib.pyplot as plt\nplt.style.use('support/visual-style/cumcm.mplstyle')\npalette=json.loads(Path('support/visual-style/palette.json').read_text())\n", encoding="utf-8")
        write(build / "evidence/problem_contracts.json", {"schema_version": "2.0", "questions": [{"question_id": "Q1", "task_verb": "predict", "requirements": [{"type": "EXPLICIT", "statement": "predict y", "basis": "problem statement", "status": "PASS"}], "inputs": ["x"], "outputs": ["y"], "metrics": ["MAE"], "constraints": [], "downstream_interfaces": [], "validation": ["holdout"], "units_status": "PASS", "time_direction": "past to future", "result_template_mapping": "result.xlsx", "status": "PASS"}], "data_fields": [{"field": "x", "meaning": "input", "unit": "1", "object": "sample", "time_basis": "day", "source": "attachment", "source_type": "PROVIDED", "source_reference": "problem.txt", "observed": True, "missing_policy": "reject", "status": "PASS"}]})
        write(build / "evidence/baselines.json", {"schema_version": "2.0", "baselines": [{"question_id": "Q1", "baseline_name": "mean", "method": "mean", "target_output": "y", "failure_conditions": ["trend"], "current_data_evidence": ["checked"], "historical_review": {"searched": True, "cases": [], "no_transfer_reason": "none suitable"}, "status": "PASS"}]})
        write(build / "evidence/model_contracts.json", {"schema_version": "2.0", "contracts": [{"formula_id": "F1", "code_path": "code/model.py", "test_path": "tests/test_contract.py", "tested_invariants": ["identity boundary"], "evidence_files": ["results/evidence.csv"], "status": "PASS"}], "assumptions": [{"assumption_id": "A1", "statement": "samples are comparable", "basis": "same protocol", "model_impact": "supports comparison", "failure_condition": "protocol changes", "critical": True, "sensitivity_ids": ["S1"], "status": "PASS"}], "symbols": [{"symbol": "x", "meaning": "input", "type": "continuous", "unit": "1", "domain": "real", "code_name": "x", "scope": "global", "status": "PASS"}]})
        write(build / "evidence/data_processing.json", {"schema_version": "2.0", "decisions": [{"decision_id": "D1", "data_scope": "results/evidence.csv", "issue": "none", "action": "KEEP", "rationale": "fixture is complete", "before_count": 1, "after_count": 1, "data_role": "OBSERVED", "evidence_files": ["results/evidence.csv"], "status": "PASS"}]})
        write(build / "evidence/experiments.json", {"schema_version": "2.0", "experiments": [{"experiment_id": "E1", "role": "FINAL_TEST", "purpose": "paired test", "data_files": ["results/evidence.csv"], "seed": 1, "sample_size": 10, "model_frozen_before_run": True, "used_for_selection": False, "comparison_id": "C1", "paired_environment_id": "ENV1", "compared_plans": ["A", "B"], "status": "PASS"}], "validation_protocols": [{"protocol_id": "V1", "question_id": "Q1", "problem_type": "PREDICTION", "metrics": ["MAE"], "metric_selection_rationale": "absolute error matches target scale", "design": "locked holdout", "thresholds": {"MAE": 1}, "evidence_files": ["results/evidence.csv"], "status": "PASS"}]})
        write(build / "evidence/optimization_certificates.json", {"schema_version": "2.0", "certificates": [{"certificate_id": "O1", "question": "Q1", "core": True, "incumbent": 99, "best_bound": 100, "sense": "max", "absolute_gap": 1, "relative_gap": 0.01, "runtime_seconds": 1, "termination": "gap", "solver": "fixture", "structure_scope": "full", "allowed_language": ["approximately optimal"], "status": "PASS"}]})
        write(build / "evidence/sensitivity.json", {"schema_version": "2.0", "analyses": [{"analysis_id": "S1", "target": "y", "perturbation_type": "variance", "decision_policy": "FIXED_PLAN", "mean_preserving": True, "range": [0.5, 1.5], "sample_size": 10, "seed": 1, "evidence_files": ["results/evidence.csv"], "status": "PASS"}]})
        write(build / "evidence/constraint_certificates.json", {"schema_version": "2.0", "certificates": [{"plan_id": "A", "constraint_id": "C1", "applicability": True, "status": "PASS", "max_violation": 0, "tolerance": 1e-8, "evidence_file": "results/evidence.csv"}]})
        write(build / "evidence/claims.json", {"schema_version": "2.0", "claims": [{"claim_id": "Q1-C1", "question": "Q1", "kind": "result", "disposition": "INCLUDE", "wording": "fixture result", "allowed_language": ["fixture"], "forbidden_language": ["universal"], "formula_ids": ["F1"], "evidence_files": ["results/evidence.csv"], "experiment_ids": ["E1"], "falsifier": "reversal", "status": "PASS"}]})
        write(build / "evidence/figures.json", {"schema_version": "2.0", "figures": [{"figure_id": "FIG1", "question": "Q1", "claim_ids": ["Q1-C1"], "claim": "fixture result", "role": "result", "source_files": ["results/evidence.csv"], "source_sha256": {"results/evidence.csv": digest(build / "results/evidence.csv")}, "fields": ["value"], "transformations": "none", "encoding": "x", "uncertainty": "none", "script": "code/figure.py", "outputs": ["figures/fig.pdf"], "paper_section": "Q1", "style_policy": "CUMCM_V1", "style_evidence": "loaded assets", "status": "FINAL"}]})
        write(build / "evidence/writing_audit.json", {"schema_version": "2.0", "strengths": [{"statement": "reproducible fixture", "evidence_files": ["results/evidence.csv"], "status": "PASS"}], "limitations": [{"statement": "small fixture", "boundary": "test only", "evidence_files": ["results/evidence.csv"], "status": "PASS"}], "consistency_checks": [{"check": name, "evidence_files": ["paper/main.tex"], "status": "PASS"} for name in ["TERMS", "SYMBOLS", "SECTION_PROMISES", "NUMBERS", "PAGE_BUDGET", "PADDING"]]})
        writing_path = build / "evidence/writing_audit.json"
        writing_payload = json.loads(writing_path.read_text(encoding="utf-8"))
        removed_check = writing_payload["consistency_checks"].pop()
        write(writing_path, writing_payload)
        writing_failure = run("evidence_audit.py", str(build), "--strict", expected=2)
        assert any("writing audit missing checks" in value for value in writing_failure["errors"])
        writing_payload["consistency_checks"].append(removed_check)
        write(writing_path, writing_payload)
        write(build / "reports/CUMCM_FORMAT_AUDIT.json", {
            "status": "PASS",
            "pdf": "paper/final.pdf",
            "pdf_sha256": digest(build / "paper/final.pdf"),
            "source": "paper/main.tex",
            "source_sha256": digest(build / "paper/main.tex"),
            "findings": [],
        })
        manifest_path = build / "project_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")); manifest["rules_snapshot"] = "fixture"; write(manifest_path, manifest)
        state_path = build / "workflow_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")); state["current_phase"] = "P8"
        for phase, record in state["phases"].items():
            if phase != "P8": record.update({"quality_status": "PASS", "user_review": "WAIVED", "report": "plan.md"})
        write(state_path, state)
        run("gate.py", str(build), "submit", "--phase", "P8", "--quality-status", "PASS", "--report", "reports/VERIFY_REPORT.md", "--summary", "fixture")
        run("gate.py", str(build), "decide", "--phase", "P8", "--decision", "waive")
        assert run("audit_project.py", str(build), "--output", "reports/FINAL_AUDIT.json")["status"] == "PASS"
        task.write_text(task.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
        stale = run("clean_build_audit.py", str(build), expected=2)
        assert any("source changed" in value for value in stale["errors"])
        passed += ["real isolated build", "stale-build detection", "red-team provenance", "85-point final threshold", "borrowed quality gates", "P8 end-to-end audit"]

    print(json.dumps({"status": "PASS", "tests": passed}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
