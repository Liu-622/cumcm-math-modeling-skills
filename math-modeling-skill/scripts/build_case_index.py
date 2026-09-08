#!/usr/bin/env python3
"""Build the portable case index from Markdown cards.

Cards use YAML frontmatter for machine-readable fields and a prose body for
reasoning. For unchanged cards, the existing generation timestamp is retained
so repeated builds do not create a meaningless diff.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REQUIRED = {
    "case_id", "paper_id", "year", "title", "competition",
    "problem_types", "models", "core_problem", "data_features",
    "validation_methods", "transferable_patterns", "source_pdf", "source_page",
    "evidence_mode",
}


def parse_card(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.S)
    if not match:
        raise ValueError(f"missing YAML frontmatter: {path}")
    meta = yaml.safe_load(match.group(1)) or {}
    missing = sorted(REQUIRED - set(meta))
    if missing:
        raise ValueError(f"{path.name}: missing fields {missing}")
    for key in ("problem_types", "models", "keywords", "validation_methods", "transferable_patterns"):
        value = meta.get(key, [])
        if isinstance(value, str):
            value = [value]
        meta[key] = [str(item).strip() for item in value if str(item).strip()]
    body = match.group(2).strip()
    searchable_body = re.sub(r"[`#>*_|\[\]()]", " ", body)
    searchable_body = re.sub(r"\s+", " ", searchable_body).strip()
    relative = path.relative_to(root).as_posix()
    entry = {
        **meta,
        "year": int(meta["year"]),
        "paper_id": str(meta["paper_id"]),
        "paper_code": str(meta.get("paper_code") or ""),
        "card_path": relative,
        "body_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "search_text": " ".join([
            str(meta.get("title") or ""),
            str(meta.get("core_problem") or ""),
            str(meta.get("data_features") or ""),
            " ".join(meta.get("problem_types") or []),
            " ".join(meta.get("models") or []),
            " ".join(meta.get("keywords") or []),
            " ".join(meta.get("validation_methods") or []),
            " ".join(meta.get("transferable_patterns") or []),
            searchable_body,
        ]),
    }
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.skill_root.resolve()
    cases_dir = root / "cases"
    paths = sorted(cases_dir.glob("case-[0-9][0-9][0-9].md"))
    if not paths:
        raise SystemExit(f"no case cards found in {cases_dir}")
    entries = [parse_card(path, root) for path in paths]
    ids = [entry["case_id"] for entry in entries]
    paper_ids = [entry["paper_id"] for entry in entries]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate case_id detected")
    if len(set(paper_ids)) != len(paper_ids):
        raise SystemExit("duplicate paper_id detected")
    entries.sort(key=lambda item: (item["year"], item["paper_code"], item["title"], item["case_id"]))
    json_path = cases_dir / "index.json"
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
        if existing.get("cases") == entries and existing.get("generated_at"):
            generated_at = str(existing["generated_at"])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "case_count": len(entries),
        "cases": entries,
    }
    json_part = json_path.with_suffix(".json.part")
    json_part.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    json_part.replace(json_path)

    csv_path = cases_dir / "index.csv"
    csv_part = csv_path.with_suffix(".csv.part")
    fields = [
        "case_id", "year", "paper_code", "paper_id", "title", "problem_types",
        "models", "validation_methods", "core_problem", "data_features",
        "card_path", "source_pdf",
    ]
    with csv_part.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for entry in entries:
            row = {key: entry.get(key, "") for key in fields}
            for key in ("problem_types", "models", "validation_methods"):
                row[key] = " | ".join(row[key] or [])
            writer.writerow(row)
    csv_part.replace(csv_path)
    md_path = cases_dir / "index.md"
    md_lines = [
        "# 优秀论文案例卡索引",
        "",
        f"共 {len(entries)} 张案例卡。按问题结构检索时优先运行 `python scripts/search_cases.py \"<赛题结构描述>\" --top 6`。",
        "",
        "| 年份 | 案例 | 题号 | 论文 | 问题类型 | 主要模型 |",
        "|---:|---|---|---|---|---|",
    ]
    for entry in entries:
        link = Path(entry["card_path"]).name
        types = "、".join(entry.get("problem_types") or [])
        models = "、".join((entry.get("models") or [])[:6])
        title = str(entry["title"]).replace("|", "\\|")
        md_lines.append(
            f"| {entry['year']} | [{entry['case_id']}]({link}) | "
            f"{entry['paper_code'] or '-'} | {title} | {types} | {models} |"
        )
    md_part = md_path.with_suffix(".md.part")
    md_part.write_text("\n".join(md_lines) + "\n", encoding="utf-8", newline="\n")
    md_part.replace(md_path)
    print(f"indexed {len(entries)} cases -> {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
