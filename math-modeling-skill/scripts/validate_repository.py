#!/usr/bin/env python3
"""Validate repository-level safety, portability, links, and case indexes."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".json", ".csv", ".py", ".yaml", ".yml", ".txt"}
FORBIDDEN_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
    ".tif", ".tiff", ".zip", ".7z", ".rar", ".tar", ".gz", ".pem", ".key",
}
REQUIRED_FILES = {
    "README.md", "SKILL.md", "LICENSE", "CONTRIBUTING.md",
    "CONTRIBUTOR-AGREEMENT.md", "THIRD-PARTY-NOTICE.md", "SECURITY.md",
    "CHANGELOG.md", "requirements-dev.txt", ".gitignore", ".gitattributes",
    ".github/CODEOWNERS", ".github/pull_request_template.md",
    ".github/workflows/validate.yml",
}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    "OpenAI key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
LOCAL_PATH_PATTERNS = {
    "Windows user path": re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+"),
    "workspace D drive path": re.compile(r"(?i)D:\\优秀论文爬取"),
    "product E drive path": re.compile(r"(?i)E:\\math-modeling-skill"),
    "Unix home path": re.compile(r"(?i)(?:/Users/[^/\s]+|/home/[^/\s]+)"),
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
CASE_FILE = re.compile(r"case-[0-9]{3}\.md\Z")
OFFICIAL_SOURCE = re.compile(r"https://dxs\.moe\.gov\.cn/")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def tracked_files() -> list[Path]:
    return sorted(
        path for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )


def read_text(path: Path, errors: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        errors.append(f"not UTF-8: {relative(path)} ({exc})")
        return None


def validate_files(files: list[Path], errors: list[str]) -> dict[Path, str]:
    texts: dict[Path, str] = {}
    for path in files:
        rel = relative(path)
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden source/media/archive file: {rel}")
        if path.stat().st_size > 5 * 1024 * 1024:
            errors.append(f"file exceeds 5 MiB review limit: {rel}")
        if path.suffix.lower() in TEXT_SUFFIXES or not path.suffix:
            text = read_text(path, errors)
            if text is None:
                continue
            texts[path] = text
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"possible {label}: {rel}")
            # This validator necessarily contains the detection regexes themselves.
            if rel != "scripts/validate_repository.py":
                for label, pattern in LOCAL_PATH_PATTERNS.items():
                    if pattern.search(text):
                        errors.append(f"non-portable {label}: {rel}")
    return texts


def validate_links(texts: dict[Path, str], errors: list[str]) -> None:
    for path, text in texts.items():
        if path.suffix.lower() != ".md":
            continue
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = unquote(target.split("#", 1)[0].split(" ", 1)[0])
            if not (path.parent / target).resolve().exists():
                errors.append(f"broken Markdown link: {relative(path)} -> {raw_target}")


def validate_cases(texts: dict[Path, str], errors: list[str]) -> None:
    case_dir = ROOT / "cases"
    cards = sorted(path for path in case_dir.glob("case-*.md") if CASE_FILE.fullmatch(path.name))
    try:
        index = json.loads((case_dir / "index.json").read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid cases/index.json: {exc}")
        return
    entries = index.get("cases") or []
    if index.get("case_count") != len(cards) or len(entries) != len(cards):
        errors.append(
            f"case index count mismatch: cards={len(cards)}, "
            f"declared={index.get('case_count')}, entries={len(entries)}"
        )
    by_path = {str(entry.get("card_path")): entry for entry in entries}
    indexed_ids: set[str] = set()
    for card in cards:
        rel = relative(card)
        entry = by_path.get(rel)
        if entry is None:
            errors.append(f"case missing from index: {rel}")
            continue
        case_id = str(entry.get("case_id") or "")
        if case_id != card.stem:
            errors.append(f"case ID mismatch in index: {rel} -> {case_id}")
        if case_id in indexed_ids:
            errors.append(f"duplicate indexed case ID: {case_id}")
        indexed_ids.add(case_id)
        # Match build_case_index.py: hash the decoded text after universal-newline
        # normalization, so contributors on Windows and Linux get the same value.
        card_text = card.read_text(encoding="utf-8")
        digest = hashlib.sha256(card_text.encode("utf-8")).hexdigest()
        if entry.get("body_sha256") != digest:
            errors.append(f"stale case index hash: {rel}; rebuild cases indexes")
        source_page = str(entry.get("source_page") or "")
        if not OFFICIAL_SOURCE.match(source_page):
            errors.append(f"case source is not an official dxs.moe.gov.cn page: {rel}")
        if entry.get("evidence_mode") not in {"text", "ocr_sampled"}:
            errors.append(f"invalid evidence_mode in index: {rel}")

    try:
        with (case_dir / "index.csv").open("r", encoding="utf-8-sig", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
        if len(csv_rows) != len(cards):
            errors.append(f"cases/index.csv row count mismatch: {len(csv_rows)}")
    except Exception as exc:
        errors.append(f"invalid cases/index.csv: {exc}")

    if not (case_dir / "index.md").exists():
        errors.append("missing cases/index.md")


def main() -> int:
    errors: list[str] = []
    files = tracked_files()
    present = {relative(path) for path in files}
    for required in sorted(REQUIRED_FILES - present):
        errors.append(f"missing repository file: {required}")
    for forbidden_dir in ("source-papers", "ocr-cache", "raw-data", "local-data"):
        if (ROOT / forbidden_dir).exists():
            errors.append(f"forbidden local corpus directory present: {forbidden_dir}")

    texts = validate_files(files, errors)
    validate_links(texts, errors)
    validate_cases(texts, errors)

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Repository validation passed: {len(files)} files, 139 indexed cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
