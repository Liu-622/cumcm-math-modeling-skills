#!/usr/bin/env python3
"""Validate the publishable CUMCM skill bundle with only the Python stdlib."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIMARY_SKILL = ROOT / "cumcm-c-national-prize-workflow"
REQUIRED_DEPENDENCIES = (
    "_references/cumcm_2026_format_spec.md",
    "1start-mathmodel/SKILL.md",
    "2analysis-modeling/SKILL.md",
    "3coding-visual/SKILL.md",
    "4drawio/SKILL.md",
    "5writing/SKILL.md",
    "6verity/SKILL.md",
    "cumcm-c-problem/SKILL.md",
    "math-modeling-skill/SKILL.md",
    "mathmodel-figure-templates/SKILL.md",
)


def frontmatter(text: str, path: Path) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    try:
        raw = text.split("---\n", 2)[1]
    except IndexError as exc:
        raise ValueError(f"{path}: unclosed YAML frontmatter") from exc

    fields: dict[str, str] = {}
    for line in raw.splitlines():
        match = re.match(r"^([a-zA-Z][a-zA-Z0-9_-]*):\s*(.+?)\s*$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip('"\'')
    return fields


def validate_skills() -> list[str]:
    names: list[str] = []
    for skill_md in sorted(ROOT.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        fields = frontmatter(text, skill_md)
        name = fields.get("name", "")
        description = fields.get("description", "")
        if name != skill_md.parent.name:
            raise ValueError(
                f"{skill_md}: name {name!r} does not match folder {skill_md.parent.name!r}"
            )
        if not description:
            raise ValueError(f"{skill_md}: missing description")
        names.append(name)

    if not names:
        raise ValueError("no top-level skills found")
    return names


def validate_dependencies() -> None:
    missing = [path for path in REQUIRED_DEPENDENCIES if not (ROOT / path).is_file()]
    if missing:
        raise ValueError("missing workflow dependencies: " + ", ".join(missing))


def validate_clean_tree() -> None:
    unwanted = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if "__pycache__" in path.parts or path.suffix == ".pyc"
    ]
    if unwanted:
        raise ValueError("generated Python files are present: " + ", ".join(unwanted))


def run_primary_self_test() -> dict[str, object]:
    script = PRIMARY_SKILL / "scripts" / "self_test.py"
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    result = json.loads(completed.stdout)
    if result.get("status") != "PASS":
        raise ValueError(f"primary workflow self-test did not pass: {result}")
    return result


def main() -> int:
    try:
        skills = validate_skills()
        validate_dependencies()
        validate_clean_tree()
        self_test = run_primary_self_test()
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"VALIDATION_FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "PASS",
                "skill_count": len(skills),
                "skills": skills,
                "primary_self_tests": len(self_test.get("tests", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
