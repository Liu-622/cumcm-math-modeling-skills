#!/usr/bin/env python3
"""Add a uniform field synopsis to cards whose reviewed prose uses aliases.

Human-reviewed OCR cards intentionally use concise labels such as “验证” or
“问题拆解”.  The skill contract, however, promises the same retrievable field
names on every card.  This mechanical pass preserves the reviewed prose and
adds only missing canonical labels before the evidence table.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


FIELDS = [
    "题目", "比赛", "年份", "问题类型", "核心问题", "数据特点", "使用模型",
    "模型选择理由", "关键公式", "算法", "问题拆解方式", "创新点", "模型验证方法",
    "论文结构亮点", "可迁移经验", "不应该机械复制的部分",
]

ALIASES = {
    "数据特点": ["数据", "数据结构"],
    "使用模型": ["模型", "建模方法"],
    "关键公式": ["关键数学表达", "公式", "数学表达"],
    "问题拆解方式": ["问题拆解", "子问题依赖", "依赖关系"],
    "模型验证方法": ["验证", "验证方法", "模型检验"],
    "论文结构亮点": ["结构亮点", "写作亮点"],
    "不应该机械复制的部分": ["不应机械复制", "不可机械复制", "不可照搬"],
}


def parse(text: str, path: Path) -> tuple[dict[str, Any], str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.S)
    if not match:
        raise ValueError(f"missing frontmatter: {path}")
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def list_text(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def alias_value(body: str, field: str) -> str:
    for alias in ALIASES.get(field, []):
        match = re.search(rf"(?m)^\s*(?:-\s*)?【{re.escape(alias)}】\s*(.+?)\s*$", body)
        if match:
            return match.group(1).strip()
    return ""


def value_for(field: str, meta: dict[str, Any], body: str) -> str:
    mapped = {
        "题目": meta.get("title"),
        "比赛": meta.get("competition"),
        "年份": meta.get("year"),
        "问题类型": meta.get("problem_types"),
        "核心问题": meta.get("core_problem"),
        "数据特点": meta.get("data_features"),
        "使用模型": meta.get("models"),
        "模型验证方法": meta.get("validation_methods"),
        "可迁移经验": meta.get("transferable_patterns"),
    }
    direct = list_text(mapped.get(field))
    if direct:
        return direct
    alias = alias_value(body, field)
    if alias:
        return alias
    defaults = {
        "模型选择理由": "见本卡“决策链”中的选择理由；只迁移与新题数据、机制和约束相符的部分。",
        "关键公式": "当前证据范围未稳定恢复可核对的原文公式；使用时须按证据锚点回源确认变量、量纲和公式，禁止臆造。",
        "算法": "见本卡“决策链”中的算法/求解步骤，并按新题数据接口补齐停止条件、随机种子与可行性检查。",
        "问题拆解方式": "见本卡“决策链”中的子问输入、输出与依赖描述；未被抽样证据覆盖的依赖需回源确认。",
        "创新点": "见本卡“可信度与创新”；复杂模型名称本身不构成创新。",
        "论文结构亮点": "摘要按子问串联任务、方法与结果；扫描抽样不足以评价全文版式，涉及正文结构时需回源核对。",
        "不应该机械复制的部分": "原论文的参数、阈值、权重、数据切分及题目专属约束，除非新题证据与机制均支持。",
    }
    return defaults.get(field, "需按证据锚点回源核对。")


def normalize_card(path: Path, check: bool) -> tuple[bool, list[str]]:
    text = path.read_text(encoding="utf-8")
    meta, body = parse(text, path)
    missing = [field for field in FIELDS if f"【{field}】" not in body]
    if not missing or check:
        return False, missing
    lines = ["## 统一案例字段", ""]
    lines.extend(f"- 【{field}】{value_for(field, meta, body)}" for field in missing)
    block = "\n".join(lines) + "\n\n"
    marker = "## 证据锚点"
    if marker in body:
        body = body.replace(marker, block + marker, 1)
    else:
        body = body.rstrip() + "\n\n" + block
    front = text.split("---", 2)[1]
    updated = f"---{front}---\n{body.rstrip()}\n"
    part = path.with_suffix(".md.part")
    part.write_text(updated, encoding="utf-8", newline="\n")
    part.replace(path)
    return True, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    paths = sorted((args.skill_root.resolve() / "cases").glob("case-[0-9][0-9][0-9].md"))
    if len(paths) != 139:
        raise SystemExit(f"expected 139 cards, found {len(paths)}")
    changed = 0
    unresolved: list[str] = []
    for path in paths:
        wrote, missing = normalize_card(path, args.check)
        changed += int(wrote)
        if args.check and missing:
            unresolved.append(f"{path.name}: {', '.join(missing)}")
    if args.check and unresolved:
        print("Canonical case fields missing:")
        print("\n".join(f"- {item}" for item in unresolved))
        return 1
    print(f"checked {len(paths)} cards; normalized {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
