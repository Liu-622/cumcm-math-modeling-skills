#!/usr/bin/env python3
"""Generate a compact corpus map from the reviewed case-card index."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any


MODEL_ALIASES = {
    "0-1规划": "0-1 规划",
    "BP神经网络": "BP 神经网络",
    "K-means": "K-Means",
    "Logistic": "Logistic 回归",
    "灰色关联": "灰色关联分析",
    "马尔可夫": "马尔可夫链",
    "排队论": "排队模型",
}

VALIDATION_ALIASES = {
    "R2": "拟合优度（R²）",
    "R²": "拟合优度（R²）",
    "拟合优度": "拟合优度（R²）",
    "灵敏度分析": "敏感性分析",
    "参数敏感性分析": "敏感性分析",
    "鲁棒性": "稳健性分析",
}


def canonical(label: Any, aliases: dict[str, str]) -> str:
    value = str(label).strip()
    return aliases.get(value, value)


def top(counter: Counter[str], limit: int = 30) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def case_label(case: dict[str, Any]) -> str:
    code = case.get("paper_code") or case["paper_id"]
    link = (Path("..") / case["card_path"]).as_posix()
    return f"[{case['case_id']}]({link}) {case['year']} {code}"


def table(counter: Counter[str], examples: dict[str, list[dict[str, Any]]], limit: int = 30) -> list[str]:
    lines = ["| 标签 | 案例数 | 代表案例 |", "|---|---:|---|"]
    for label, count in top(counter, limit):
        refs = "；".join(case_label(case) for case in examples[label][:4])
        lines.append(f"| {label} | {count} | {refs} |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.skill_root.resolve()
    payload = json.loads((root / "cases" / "index.json").read_text(encoding="utf-8"))
    cases = payload["cases"]
    if len(cases) != 139:
        raise SystemExit(f"expected 139 cases, found {len(cases)}")

    years: Counter[str] = Counter()
    types: Counter[str] = Counter()
    models: Counter[str] = Counter()
    validations: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    year_modes: dict[str, Counter[str]] = defaultdict(Counter)
    pairs: Counter[str] = Counter()
    type_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    model_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    validation_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for case in cases:
        years[str(case["year"])] += 1
        evidence_mode = str(case.get("evidence_mode") or "unknown")
        modes[evidence_mode] += 1
        year_modes[str(case["year"])][evidence_mode] += 1
        for label in sorted(set(case.get("problem_types") or [])):
            types[label] += 1
            type_examples[label].append(case)
        case_models = sorted({canonical(label, MODEL_ALIASES) for label in case.get("models") or []})
        for label in case_models:
            models[label] += 1
            model_examples[label].append(case)
        for label in sorted({canonical(item, VALIDATION_ALIASES) for item in case.get("validation_methods") or []}):
            validations[label] += 1
            validation_examples[label].append(case)
        for left, right in combinations(case_models[:12], 2):
            pairs[f"{left} ↔ {right}"] += 1

    json_path = root / "knowledge" / "corpus-analysis.json"
    content = {
        "schema_version": 1,
        "case_count": len(cases),
        "by_year": dict(sorted(years.items())),
        "evidence_by_year": {
            year: dict(top(counts, 20)) for year, counts in sorted(year_modes.items())
        },
        "evidence_modes": dict(top(modes, 20)),
        "problem_types": dict(top(types, 100)),
        "models": dict(top(models, 200)),
        "validation_methods": dict(top(validations, 200)),
        "model_pairs": dict(top(pairs, 100)),
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
        existing_content = {key: value for key, value in existing.items() if key != "generated_at"}
        if existing_content == content and existing.get("generated_at"):
            generated_at = str(existing["generated_at"])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    data = {
        "schema_version": content.pop("schema_version"),
        "generated_at": generated_at,
        **content,
    }
    json_part = json_path.with_suffix(".json.part")
    json_part.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    json_part.replace(json_path)

    lines = [
        "# 139 篇优秀论文案例库观察图谱",
        "",
        f"> 由 `cases/index.json` 于 {generated_at} 自动生成。统计对象是案例卡标签，",
        "> 用于检索与审计，不代表某模型更优，也不能替代原论文的页码证据。",
        "",
        "## 语料边界",
        "",
        f"- 案例卡：{len(cases)} 张；年份：{min(years)}—{max(years)}。",
        f"- 证据方式：{'；'.join(f'{key} {value}' for key, value in top(modes, 20))}。",
        "- 同一论文可有多个问题类型、模型和验证标签，因此以下计数不可相加为论文总数。",
        "- 先按问题结构检索，再打开案例卡核对选择理由、适用边界与证据锚点。",
        "",
        "## 年份与证据覆盖",
        "",
        "| 年份 | 案例数 | 全文文本卡 | OCR 抽样卡 | 其他/未知 |",
        "|---:|---:|---:|---:|---:|",
        *[
            f"| {year} | {years[year]} | {year_modes[year].get('text', 0)} | "
            f"{year_modes[year].get('ocr_sampled', 0)} | "
            f"{sum(value for key, value in year_modes[year].items() if key not in {'text', 'ocr_sampled'})} |"
            for year in sorted(years)
        ],
        "",
        "## 问题类型分布与代表案例",
        "",
        *table(types, type_examples, 30),
        "",
        "## 模型与方法标签",
        "",
        *table(models, model_examples, 50),
        "",
        "## 验证方法标签",
        "",
        *table(validations, validation_examples, 40),
        "",
        "## 高频模型共现（仅作候选组合线索）",
        "",
        "| 模型对 | 共现案例数 |",
        "|---|---:|",
        *[f"| {label} | {count} |" for label, count in top(pairs, 40)],
        "",
        "## 正确使用方式",
        "",
        "1. 用新题的目标、数据结构、约束、时间/空间/网络关系和不确定性形成检索词。",
        "2. 读取 3—8 张结构相似卡，比较决策链而非只数模型出现次数。",
        "3. 将案例中的阈值、权重、参数和题目专属机制视为不可直接迁移信息。",
        "4. 对 OCR 抽样卡或低置信度锚点，必要时回到源 PDF 补充核对。",
        "5. 把案例库中未执行的验证视为缺口，不替作者补写为已完成实验。",
        "",
    ]
    md_path = root / "knowledge" / "corpus-analysis.md"
    md_part = md_path.with_suffix(".md.part")
    md_part.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    md_part.replace(md_path)
    print(f"generated corpus map for {len(cases)} cases -> {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
