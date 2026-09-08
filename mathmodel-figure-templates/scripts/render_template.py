#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_MAP = {
    "multiclass-shap-combo": "make_multiclass_shap_combo.py",
    "paired-raincloud": "make_paired_raincloud.py",
    "cv-roc-ci": "make_cv_roc_ci.py",
    "taylor-diagram": "make_taylor_diagram.py",
    "correlation-pairgrid": "make_correlation_pairgrid.py",
    "prediction-marginal-grid": "make_prediction_marginal_grid.py",
    "rf-tpe-surface": "make_rf_tpe_surface.py",
    "grouped-corr-split-violin": "make_grouped_corr_split_violin.py",
    "grouped-circular-heatmap": "make_grouped_circular_heatmap.py",
    "urban-park-cooling-combo": "make_urban_park_cooling_combo.py",
    "nature-chord-diagram": "make_nature_chord_diagram.py",
}

ALIASES = {
    "shap": "multiclass-shap-combo",
    "multiclass-shap": "multiclass-shap-combo",
    "raincloud": "paired-raincloud",
    "roc": "cv-roc-ci",
    "cv-roc": "cv-roc-ci",
    "taylor": "taylor-diagram",
    "pairgrid": "correlation-pairgrid",
    "correlation": "correlation-pairgrid",
    "pred-true": "prediction-marginal-grid",
    "prediction": "prediction-marginal-grid",
    "surface": "rf-tpe-surface",
    "tpe": "rf-tpe-surface",
    "split-violin": "grouped-corr-split-violin",
    "circular-heatmap": "grouped-circular-heatmap",
    "urban-cooling": "urban-park-cooling-combo",
    "chord": "nature-chord-diagram",
    "circos": "nature-chord-diagram",
}

CJK_HINTS = {
    "多分类": "multiclass-shap-combo",
    "shap": "multiclass-shap-combo",
    "云雨": "paired-raincloud",
    "roc": "cv-roc-ci",
    "泰勒": "taylor-diagram",
    "相关矩阵组合": "correlation-pairgrid",
    "拟合线": "correlation-pairgrid",
    "预测": "prediction-marginal-grid",
    "真实": "prediction-marginal-grid",
    "tpe": "rf-tpe-surface",
    "曲面": "rf-tpe-surface",
    "半边小提琴": "grouped-corr-split-violin",
    "环形热图": "grouped-circular-heatmap",
    "城市公园": "urban-park-cooling-combo",
    "堆叠": "urban-park-cooling-combo",
    "和弦": "nature-chord-diagram",
    "circos": "nature-chord-diagram",
}


def normalize(value: str) -> str:
    value = value.strip().lower().replace("_", "-")
    value = re.sub(r"[^a-z0-9\-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def resolve_template(value: str) -> str:
    raw = value.strip()
    key = normalize(raw)
    if key in SCRIPT_MAP:
        return key
    if key in ALIASES:
        return ALIASES[key]
    lowered = raw.lower()
    for hint, template_id in CJK_HINTS.items():
        if hint.lower() in lowered:
            return template_id
    raise SystemExit(
        f"Unknown template: {value}\nAvailable ids: " + ", ".join(sorted(SCRIPT_MAP))
    )


def write_readme(project: Path, template_id: str, script_path: Path, outputs_dir: Path, *, workflow: bool) -> None:
    readme = project / "README.md"
    output_stem = outputs_dir / f"{script_path.stem.removeprefix('make_')}_replica"
    output_stem_rel = output_stem.relative_to(project)
    script_rel = script_path.relative_to(project).as_posix()
    block = f"""
## {template_id}

Generated from the bundled MathModel figure-template skill.

Bundled templates use deterministic simulated data. These outputs are demonstrations, not measured study results, unless the workspace script has been adapted to validated task data.

Run from this project directory with the same Python environment used for rendering:

```text
python -X utf8 "{script_rel}"
```

Outputs:

- `{output_stem_rel.with_suffix('.png').as_posix()}`
- `{output_stem_rel.with_suffix('.pdf').as_posix()}`
- `{output_stem_rel.with_suffix('.svg').as_posix()}`
""".strip()
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        marker = f"## {template_id}"
        if marker in text:
            return
        readme.write_text(text.rstrip() + "\n\n" + block + "\n", encoding="utf-8")
    else:
        title = "# 建模项目图表" if workflow else "# 绘图复刻"
        readme.write_text(title + "\n\n" + block + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a bundled MathModel figure template.")
    parser.add_argument("template", nargs="?", help="Template id, alias, or Chinese title fragment")
    parser.add_argument("--project", default="绘图复刻", help="Output directory, or modeling-project root with --workflow")
    parser.add_argument("--workflow", action="store_true", help="Use code/figures, figures, and evidence/figures.json in a modeling project")
    parser.add_argument("--prepare", action="store_true", help="With --workflow, copy the template script without rendering or registration")
    parser.add_argument("--confirm-real-data", action="store_true", help="Confirm the workflow script uses validated task data; required before registration")
    parser.add_argument("--figure-id", help="Figure registry id; required for workflow registration")
    parser.add_argument("--question", help="Question id; required for workflow registration")
    parser.add_argument("--claim-id", action="append", default=[], help="Existing PASS+INCLUDE claim id; repeat as needed")
    parser.add_argument("--claim", help="Falsifiable figure claim; required for workflow registration")
    parser.add_argument("--role", default="result", help="Figure role in the paper")
    parser.add_argument("--source-file", action="append", default=[], help="Project-relative validated source file; repeat as needed")
    parser.add_argument("--paper-section", help="Paper section; required for workflow registration")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing copied workspace script")
    parser.add_argument("--list", action="store_true", help="List supported template ids")
    args = parser.parse_args()

    if args.list:
        for template_id in sorted(SCRIPT_MAP):
            print(template_id)
        return
    if not args.template:
        parser.error("template is required unless --list is used")
    if args.prepare and not args.workflow:
        parser.error("--prepare is only valid with --workflow")

    template_id = resolve_template(args.template)
    skill_root = Path(__file__).resolve().parents[1]
    src = skill_root / "scripts" / "templates" / SCRIPT_MAP[template_id]
    if not src.exists():
        raise SystemExit(f"Bundled script missing: {src}")

    project = Path(args.project).expanduser().resolve()
    scripts_dir = project / ("code/figures" if args.workflow else "scripts")
    outputs_dir = project / ("figures" if args.workflow else "outputs")
    mpl_dir = project / ".mplconfig"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    mpl_dir.mkdir(parents=True, exist_ok=True)

    dst = scripts_dir / src.name
    if dst.exists() and not args.overwrite:
        print(f"Using existing workspace script: {dst}")
    else:
        shutil.copy2(src, dst)
        print(f"Copied template script: {dst}")

    if args.workflow:
        text = dst.read_text(encoding="utf-8")
        workflow_text = text.replace('ROOT / "outputs"', 'ROOT.parent / "figures"')
        if workflow_text == text and 'ROOT.parent / "figures"' not in text:
            raise SystemExit("Cannot adapt bundled output path for workflow mode")
        if workflow_text != text:
            dst.write_text(workflow_text, encoding="utf-8")
        if args.prepare:
            print("Prepared workflow script. Replace simulated data with validated task data before registration.")
            return
        required = {
            "--figure-id": args.figure_id,
            "--question": args.question,
            "--claim-id": args.claim_id,
            "--claim": args.claim,
            "--source-file": args.source_file,
            "--paper-section": args.paper_section,
        }
        missing_args = [name for name, value in required.items() if not value]
        if missing_args:
            parser.error("workflow registration requires " + ", ".join(missing_args))
        if not args.confirm_real_data:
            parser.error("workflow registration requires --confirm-real-data after replacing simulated data")

    result = subprocess.run([sys.executable, "-X", "utf8", str(dst)], cwd=str(project), check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    stem = dst.stem.removeprefix("make_")
    expected = [outputs_dir / f"{stem}_replica{suffix}" for suffix in (".png", ".pdf", ".svg")]
    missing = [str(path) for path in expected if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise SystemExit("Renderer completed without the expected non-empty outputs: " + ", ".join(missing))

    write_readme(project, template_id, dst, outputs_dir, workflow=args.workflow)
    if args.workflow:
        register_workflow_figure(project, template_id, dst, expected, args)
    for path in expected:
        print(path)


def relative_project_path(project: Path, value: Path | str, *, must_exist: bool = True) -> tuple[Path, str]:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = project / candidate
    candidate = candidate.resolve()
    try:
        rel = candidate.relative_to(project).as_posix()
    except ValueError as exc:
        raise SystemExit(f"Path escapes modeling project: {value}") from exc
    if must_exist and not candidate.is_file():
        raise SystemExit(f"Required project file missing: {rel}")
    return candidate, rel


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_workflow_figure(
    project: Path, template_id: str, script: Path, outputs: list[Path], args: argparse.Namespace
) -> None:
    registry_path = project / "evidence/figures.json"
    claims_path = project / "evidence/claims.json"
    if not registry_path.is_file() or not claims_path.is_file():
        raise SystemExit("Workflow registration requires evidence/figures.json and evidence/claims.json")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    claims_payload = json.loads(claims_path.read_text(encoding="utf-8"))
    claims = {item.get("claim_id"): item for item in claims_payload.get("claims", [])}
    for claim_id in args.claim_id:
        item = claims.get(claim_id)
        if not item or item.get("status") != "PASS" or item.get("disposition") != "INCLUDE":
            raise SystemExit(f"Claim must exist with PASS+INCLUDE before registration: {claim_id}")
    sources = [relative_project_path(project, value) for value in args.source_file]
    _, script_rel = relative_project_path(project, script)
    output_rels = [relative_project_path(project, value)[1] for value in outputs]
    entry = {
        "figure_id": args.figure_id,
        "question": args.question,
        "claim_ids": args.claim_id,
        "claim": args.claim,
        "role": args.role,
        "source_files": [rel for _, rel in sources],
        "source_sha256": {rel: sha256(path) for path, rel in sources},
        "fields": [],
        "transformations": "Documented in the adapted plotting script",
        "encoding": "Documented in the adapted plotting script",
        "uncertainty": "Documented in the adapted plotting script",
        "script": script_rel,
        "outputs": output_rels,
        "paper_section": args.paper_section,
        "style_policy": "TEMPLATE",
        "style_evidence": "Bundled MathModel template with paper-ready palette; verify final rendering",
        "template_id": template_id,
        "status": "GENERATED",
    }
    figures = registry.setdefault("figures", [])
    for index, existing in enumerate(figures):
        if existing.get("figure_id") == args.figure_id:
            figures[index] = entry
            break
    else:
        figures.append(entry)
    temp_path = registry_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(registry_path)
    print(f"Registered figure: {args.figure_id} ({template_id})")


if __name__ == "__main__":
    main()
