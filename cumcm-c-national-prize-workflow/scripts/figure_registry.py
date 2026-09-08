#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import digest, emit, project_relative

REQUIRED = [
    "figure_id", "question", "claim_ids", "claim", "role", "source_files", "source_sha256",
    "fields", "transformations", "encoding", "uncertainty", "script", "outputs", "paper_section",
    "style_policy", "style_evidence", "status",
]


def audit(project: Path) -> int:
    path = project / "evidence/figures.json"
    claims_path = project / "evidence/claims.json"
    if not path.is_file():
        emit({"status": "FAIL", "errors": ["evidence/figures.json missing"]})
        return 2
    payload = json.loads(path.read_text(encoding="utf-8"))
    claims_payload = json.loads(claims_path.read_text(encoding="utf-8")) if claims_path.is_file() else {"claims": []}
    claims = {item.get("claim_id"): item for item in claims_payload.get("claims", [])}
    figures = payload.get("figures", [])
    errors: list[str] = []
    warnings: list[str] = []
    ids: set[str] = set()
    if payload.get("schema_version") != "2.0":
        errors.append("figures registry schema_version must be 2.0")
    for index, figure in enumerate(figures):
        missing = [key for key in REQUIRED if key not in figure]
        if missing:
            errors.append(f"figure[{index}] missing: {', '.join(missing)}")
        figure_id = figure.get("figure_id")
        if figure_id in ids:
            errors.append(f"duplicate figure_id: {figure_id}")
        ids.add(figure_id)
        if not str(figure.get("claim", "")).strip():
            errors.append(f"{figure_id}: empty falsifiable claim")
        claim_ids = figure.get("claim_ids")
        if not isinstance(claim_ids, list) or not claim_ids:
            errors.append(f"{figure_id}: claim_ids must be non-empty")
        elif figure.get("status") in {"GENERATED", "FINAL"}:
            for claim_id in claim_ids:
                if claim_id not in claims:
                    errors.append(f"{figure_id}: unknown claim_id {claim_id}")
                elif claims[claim_id].get("status") != "PASS":
                    errors.append(f"{figure_id}: claim is not PASS: {claim_id}")
                elif claims[claim_id].get("disposition") != "INCLUDE":
                    errors.append(f"{figure_id}: claim is excluded from paper: {claim_id}")
        hashes = figure.get("source_sha256", {})
        for rel in figure.get("source_files", []):
            try:
                candidate, normalized = project_relative(project, rel, must_exist=False)
            except ValueError:
                errors.append(f"{figure_id}: source path escapes project: {rel}")
                continue
            if not candidate.exists():
                warnings.append(f"{figure_id}: source not found yet: {rel}")
            elif figure.get("status") in {"GENERATED", "FINAL"}:
                expected = hashes.get(rel)
                if not expected:
                    errors.append(f"{figure_id}: missing source hash for {rel}")
                elif candidate.is_file() and digest(candidate) != expected:
                    errors.append(f"{figure_id}: source hash changed: {rel}")
        if figure.get("status") in {"GENERATED", "FINAL"}:
            try:
                script, _ = project_relative(project, str(figure.get("script", "")), must_exist=True)
            except (ValueError, FileNotFoundError):
                script = project
            if not script.is_file():
                errors.append(f"{figure_id}: script missing: {figure.get('script')}")
            for rel in figure.get("outputs", []):
                try:
                    output, _ = project_relative(project, rel, must_exist=True)
                except (ValueError, FileNotFoundError):
                    output = project
                if not output.is_file():
                    errors.append(f"{figure_id}: output missing: {rel}")
            policy = figure.get("style_policy")
            if policy == "CUMCM_V1":
                style = project / "support/visual-style/cumcm.mplstyle"
                palette = project / "support/visual-style/palette.json"
                if not style.is_file() or not palette.is_file():
                    errors.append(f"{figure_id}: CUMCM style assets are missing")
                elif script.is_file():
                    source_text = script.read_text(encoding="utf-8", errors="replace")
                    if "cumcm.mplstyle" not in source_text or "palette.json" not in source_text:
                        errors.append(f"{figure_id}: script does not load both registered style assets")
            elif policy == "TEMPLATE":
                template_id = figure.get("template_id")
                if not isinstance(template_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", template_id):
                    errors.append(f"{figure_id}: TEMPLATE figures require a valid template_id")
                if not str(figure.get("style_evidence", "")).strip():
                    errors.append(f"{figure_id}: TEMPLATE figures require style_evidence naming the palette or customization")
            elif policy == "EXEMPT":
                if not str(figure.get("style_evidence", "")).strip():
                    errors.append(f"{figure_id}: style exemption requires evidence or rationale")
            else:
                errors.append(f"{figure_id}: invalid style_policy")
    status = "PASS" if not errors else "FAIL"
    emit({"status": status, "figures": len(figures), "errors": errors, "warnings": warnings, "manual_limit": "Registry audit cannot prove visual or numerical correctness."})
    return 0 if not errors else 2


def template() -> dict:
    value = {key: ([] if key in {"claim_ids", "source_files", "fields", "outputs"} else "") for key in REQUIRED}
    value["source_sha256"] = {}
    value["template_id"] = ""
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the C-question figure registry.")
    parser.add_argument("command", choices=["audit", "template"])
    parser.add_argument("project")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    if args.command == "template":
        emit(template())
        return 0
    return audit(project)


if __name__ == "__main__":
    raise SystemExit(main())
