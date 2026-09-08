#!/usr/bin/env python3
"""Retrieve structurally similar modeling cases from cases/index.json."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


ALIASES = {
    "预测": ["prediction", "forecast", "回归", "时间序列"],
    "评价": ["evaluation", "ranking", "综合评价", "决策"],
    "优化": ["optimization", "最优", "调度", "规划", "分配"],
    "分类": ["classification", "判别", "识别"],
    "聚类": ["clustering", "分群"],
    "网络": ["network", "graph", "路径", "节点", "运输"],
    "机理": ["mechanism", "ode", "pde", "动力学", "微分方程"],
    "仿真": ["simulation", "monte carlo", "蒙特卡洛", "随机模拟"],
    "小样本": ["small sample", "灰色预测", "bootstrap"],
    "多目标": ["multi-objective", "pareto", "nsga", "epsilon constraint"],
    "不确定性": ["uncertainty", "robust", "稳健", "敏感性", "scenario"],
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("＋", "+")).strip()


def tokens(text: str) -> list[str]:
    text = normalize(text)
    words = re.findall(r"[a-z][a-z0-9+.-]{1,}|\d+(?:\.\d+)?", text)
    chunks = re.findall(r"[\u3400-\u9fff]+", text)
    chinese: list[str] = []
    for chunk in chunks:
        chinese.extend(chunk[index:index + 2] for index in range(max(1, len(chunk) - 1)))
        chinese.extend(term for term in ALIASES if term in chunk)
    expanded = words + chinese
    for canonical, variants in ALIASES.items():
        if canonical in text or any(variant in text for variant in variants):
            expanded.append(f"tag:{canonical}")
    return expanded


def field_text(case: dict[str, Any]) -> str:
    return " ".join([
        str(case.get("title") or ""),
        str(case.get("core_problem") or ""),
        str(case.get("data_features") or ""),
        " ".join(case.get("problem_types") or []),
        " ".join(case.get("models") or []),
        " ".join(case.get("keywords") or []),
        " ".join(case.get("validation_methods") or []),
        " ".join(case.get("transferable_patterns") or []),
        str(case.get("search_text") or ""),
    ])


def score_cases(query: str, cases: list[dict[str, Any]]) -> list[tuple[float, dict[str, Any], list[str]]]:
    query_tokens = tokens(query)
    if not query_tokens:
        return []
    documents = [Counter(tokens(field_text(case))) for case in cases]
    document_frequency = Counter()
    for document in documents:
        document_frequency.update(document.keys())
    query_counts = Counter(query_tokens)
    count = len(cases)
    ranked: list[tuple[float, dict[str, Any], list[str]]] = []
    for case, document in zip(cases, documents):
        score = 0.0
        matched: list[str] = []
        for token, query_weight in query_counts.items():
            frequency = document.get(token, 0)
            if not frequency:
                continue
            inverse = math.log((count + 1) / (document_frequency[token] + 0.5)) + 1
            boost = 3.5 if token.startswith("tag:") else 1.0
            score += query_weight * inverse * boost * (1 + math.log(frequency))
            matched.append(token.removeprefix("tag:"))
        normalized_query = normalize(query)
        for value in (case.get("problem_types") or []) + (case.get("models") or []):
            if normalize(str(value)) and normalize(str(value)) in normalized_query:
                score += 4.0
        if score > 0:
            ranked.append((score, case, sorted(set(matched))))
    ranked.sort(key=lambda item: (-item[0], -int(item[1]["year"]), item[1]["case_id"]))
    return ranked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top", type=int, default=6)
    parser.add_argument("--year", type=int)
    parser.add_argument("--type", dest="problem_type")
    parser.add_argument("--model")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    index_path = args.skill_root.resolve() / "cases" / "index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if args.year:
        cases = [case for case in cases if int(case["year"]) == args.year]
    if args.problem_type:
        needle = normalize(args.problem_type)
        cases = [case for case in cases if needle in normalize(" ".join(case.get("problem_types") or []))]
    if args.model:
        needle = normalize(args.model)
        cases = [case for case in cases if needle in normalize(" ".join(case.get("models") or []))]
    ranked = score_cases(args.query, cases)[:max(1, args.top)]
    if args.json:
        print(json.dumps([
            {"score": round(score, 3), "matched": matched, **case}
            for score, case, matched in ranked
        ], ensure_ascii=False, indent=2))
        return 0
    if not ranked:
        print("No matching cases.")
        return 1
    for index, (score, case, matched) in enumerate(ranked, start=1):
        print(
            f"{index}. [{case['case_id']}] {case['year']} "
            f"{case.get('paper_code') or '-'} {case['title']}\n"
            f"   score={score:.2f}; types={', '.join(case.get('problem_types') or [])}; "
            f"models={', '.join((case.get('models') or [])[:8])}\n"
            f"   matched={', '.join(matched[:12])}; card={case['card_path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
