#!/usr/bin/env python3
"""Validate the portable modeling skill beyond basic frontmatter checks."""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml


EXPECTED_BY_YEAR = {
    2012: 3, 2013: 8, 2014: 9, 2015: 14, 2016: 5, 2017: 2,
    2018: 12, 2019: 9, 2020: 13, 2021: 17, 2022: 11,
    2023: 13, 2024: 16, 2025: 7,
}
REQUIRED_KNOWLEDGE = {
    "problem-types.md", "model-selection.md", "model-library.md",
    "model-combinations.md", "innovation-patterns.md", "paper-writing.md",
    "validation-methods.md", "problem-dependencies.md", "data-workflow.md",
    "corpus-analysis.md",
}
REQUIRED_TEMPLATES = {
    "problem-analysis.md", "model-design.md", "paper-outline.md",
    "abstract-template.md", "validation-plan.md", "case-card-template.md",
}
REQUIRED_CODE = {
    "prediction/pipeline.py", "optimization/problem.py", "evaluation/mcda.py",
    "clustering/pipeline.py", "machine-learning/supervised.py",
    "simulation/monte_carlo.py", "network/network_model.py", "mechanism/ode_model.py",
}
CARD_HEADINGS = {
    "## 基本信息", "## 决策链", "## 可信度与创新",
    "## 迁移规则", "## 证据锚点",
}
CARD_LABELS = {
    "【题目】", "【比赛】", "【年份】", "【问题类型】", "【核心问题】", "【数据特点】",
    "【使用模型】", "【模型选择理由】", "【关键公式】", "【算法】", "【问题拆解方式】",
    "【创新点】", "【模型验证方法】", "【论文结构亮点】", "【可迁移经验】",
    "【不应该机械复制的部分】",
}
FORBIDDEN_MARKERS = ("[TODO", "TODO:", "TBD", "待补充", "待人工", "待案例卡交叉验证")


def frontmatter(text: str, path: Path) -> tuple[dict, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.S)
    if not match:
        raise ValueError(f"missing frontmatter: {path}")
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []

    for path in root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file():
            try:
                if path.suffix.lower() in {".md", ".yaml", ".yml", ".json", ".csv", ".py"}:
                    path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError as exc:
                errors.append(f"not UTF-8: {path.relative_to(root)} ({exc})")
        if path.name in {"__pycache__", ".pytest_cache"} or path.suffix in {".pyc", ".part"}:
            errors.append(f"intermediate artifact present: {path.relative_to(root)}")

    skill_path = root / "SKILL.md"
    try:
        skill_text = skill_path.read_text(encoding="utf-8")
        skill_meta, skill_body = frontmatter(skill_text, skill_path)
        if set(skill_meta) != {"name", "description"}:
            errors.append("SKILL.md frontmatter must contain only name and description")
        if skill_meta.get("name") != "math-modeling-skill":
            errors.append("unexpected skill name")
        if len(skill_body.splitlines()) > 500:
            errors.append("SKILL.md body exceeds 500 lines")
        for link in re.findall(r"\[[^]]+\]\(([^)]+)\)", skill_body):
            if "://" not in link and not (root / link).exists():
                errors.append(f"broken SKILL.md link: {link}")
    except Exception as exc:
        errors.append(f"SKILL.md invalid: {exc}")

    try:
        openai = yaml.safe_load((root / "agents" / "openai.yaml").read_text(encoding="utf-8"))
        prompt = str(openai["interface"]["default_prompt"])
        if "$math-modeling-skill" not in prompt:
            errors.append("agents/openai.yaml default_prompt does not name the skill")
    except Exception as exc:
        errors.append(f"agents/openai.yaml invalid: {exc}")

    knowledge = root / "knowledge"
    missing = sorted(REQUIRED_KNOWLEDGE - {path.name for path in knowledge.glob("*.md")})
    if missing:
        errors.append(f"missing knowledge files: {missing}")
    templates = root / "templates"
    missing = sorted(REQUIRED_TEMPLATES - {path.name for path in templates.glob("*.md")})
    if missing:
        errors.append(f"missing templates: {missing}")
    code = root / "code"
    present_code = {path.relative_to(code).as_posix() for path in code.rglob("*.py")}
    missing = sorted(REQUIRED_CODE - present_code)
    if missing:
        errors.append(f"missing code scaffolds: {missing}")
    if not (root / "references" / "corpus-provenance.md").exists():
        errors.append("missing references/corpus-provenance.md")

    cards = sorted((root / "cases").glob("case-[0-9][0-9][0-9].md"))
    if len(cards) != 139:
        errors.append(f"expected 139 case cards, found {len(cards)}")
    years: Counter[int] = Counter()
    case_ids: set[str] = set()
    paper_ids: set[str] = set()
    for path in cards:
        try:
            text = path.read_text(encoding="utf-8")
            meta, body = frontmatter(text, path)
            for key in (
                "case_id", "paper_id", "year", "title", "competition",
                "problem_types", "models", "core_problem", "data_features",
                "validation_methods", "transferable_patterns", "source_pdf", "source_page",
                "evidence_mode",
            ):
                if key not in meta or meta[key] in (None, "", []):
                    errors.append(f"{path.name}: empty {key}")
            for heading in CARD_HEADINGS:
                if heading not in body:
                    errors.append(f"{path.name}: missing heading {heading}")
            for label in CARD_LABELS:
                if label not in body:
                    errors.append(f"{path.name}: missing canonical field {label}")
            if any(marker in text for marker in FORBIDDEN_MARKERS):
                errors.append(f"{path.name}: unresolved placeholder marker")
            case_id = str(meta.get("case_id"))
            paper_id = str(meta.get("paper_id"))
            if case_id != path.stem:
                errors.append(f"{path.name}: case_id {case_id!r} does not match filename")
            if case_id in case_ids:
                errors.append(f"duplicate case_id: {case_id}")
            if paper_id in paper_ids:
                errors.append(f"duplicate paper_id: {paper_id}")
            case_ids.add(case_id)
            paper_ids.add(paper_id)
            years[int(meta.get("year"))] += 1
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    if dict(sorted(years.items())) != EXPECTED_BY_YEAR:
        errors.append(f"case year counts differ: {dict(sorted(years.items()))}")

    index_path = root / "cases" / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if index.get("case_count") != 139 or len(index.get("cases") or []) != 139:
            errors.append("cases/index.json does not contain 139 cases")
    except Exception as exc:
        errors.append(f"cases/index.json invalid: {exc}")
    for name in ("index.csv", "index.md"):
        if not (root / "cases" / name).exists():
            errors.append(f"missing cases/{name}")

    for path in [*(root / "scripts").glob("*.py"), *code.rglob("*.py")]:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"Python syntax error in {path.name}: {exc}")

    for marker in FORBIDDEN_MARKERS:
        for path in [*knowledge.glob("*.md"), *templates.glob("*.md"), skill_path]:
            if path.exists() and marker in path.read_text(encoding="utf-8"):
                errors.append(f"unresolved marker {marker!r}: {path.relative_to(root)}")

    if errors:
        print("Skill content validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    total_bytes = sum(
        path.stat().st_size
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    print(f"Skill content validation passed: 139 cases, {total_bytes} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
