#!/usr/bin/env python3
"""Check CUMCM 2026 format and the configured 25-28 page requirement.

This checker is intentionally strict. It does not replace visual inspection,
mathematical review, source-code review, or the current official rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

MAX_BYTES = 20 * 1024 * 1024
A4_WIDTH_PT = 595.28
A4_HEIGHT_PT = 841.89
A4_TOLERANCE_PT = 4.0
MARGIN_PT = 2.5 / 2.54 * 72.0
MARGIN_TOLERANCE_PT = 2.0

FRONT_MATTER_MARKERS = (
    "承诺书",
    "编号专用页",
    "赛区评阅编号",
    "全国评阅编号",
    "报名参赛队号",
)
IDENTITY_MARKERS = (
    "参赛学校",
    "参赛队员",
    "指导教师",
    "报名参赛队号",
    "赛区评阅编号",
    "全国评阅编号",
)
CODE_SUFFIXES = {
    ".py", ".ipynb", ".m", ".r", ".jl", ".c", ".cc", ".cpp",
    ".h", ".hpp", ".java", ".cs", ".go", ".rs", ".f", ".f90",
    ".sps", ".do", ".sas", ".sql", ".xlsx", ".xls", ".xlsm",
}
CODE_PATTERNS = (
    r"(?m)^\s*(?:def|class|import|from)\s+",
    r"(?m)^\s*(?:function|clc\s*;|clear\s*;|library\s*\()",
    r"(?m)^\s*(?:#include|int\s+main\s*\(|public\s+static\s+void\s+main)",
    r"(?m)^\s*(?:SELECT|CREATE\s+TABLE|BEGIN\s+PROGRAM)\b",
)


@dataclass
class Finding:
    level: str
    check: str
    message: str


class Audit:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def pass_(self, check: str, message: str) -> None:
        self.findings.append(Finding("PASS", check, message))

    def warn(self, check: str, message: str) -> None:
        self.findings.append(Finding("WARN", check, message))

    def fail(self, check: str, message: str) -> None:
        self.findings.append(Finding("FAIL", check, message))

    @property
    def failed(self) -> bool:
        return any(item.level == "FAIL" for item in self.findings)


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_lines(text: str) -> list[str]:
    return [compact(line) for line in (text or "").splitlines() if compact(line)]


def has_standalone_heading(text: str, heading: str, first_n: int = 80) -> bool:
    target = compact(heading)
    return any(line == target for line in normalized_lines(text)[:first_n])


def find_appendix_page(page_texts: list[str]) -> int | None:
    for index, text in enumerate(page_texts[1:], start=1):
        for line in normalized_lines(text)[:30]:
            if re.fullmatch(r"附录(?:[A-Z一二三四五六七八九十]?)", line):
                return index
            if line.startswith("附录A") or line.startswith("附录一"):
                return index
    return None


def strip_source_comments(text: str, suffix: str) -> str:
    if suffix == ".tex":
        return re.sub(r"(?m)(?<!\\)%.*$", "", text)
    if suffix == ".typ":
        return re.sub(r"(?m)//.*$", "", text)
    return text


def inspect_source(path: Path, audit: Audit) -> None:
    check = "source"
    if not path.exists():
        audit.fail(check, f"Source file does not exist: {path}")
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    active = strip_source_comments(text, path.suffix.lower())
    if path.suffix.lower() == ".tex" and re.search(r"\\tableofcontents\b", active):
        audit.fail(check, "Active LaTeX table of contents command found.")
    elif path.suffix.lower() == ".typ":
        active_lines = [line.strip() for line in active.splitlines()]
        if any(re.fullmatch(r"#toc-page\s*\(\s*\)", line) for line in active_lines):
            audit.fail(check, "Active Typst table of contents call found.")
        elif any(re.match(r"#outline\s*\(", line) for line in active_lines):
            audit.fail(check, "Active Typst outline/table of contents call found.")
        else:
            audit.pass_(check, "No active Typst table of contents call found.")
    else:
        audit.pass_(check, "No active LaTeX table of contents command found.")

    if any(marker in text for marker in IDENTITY_MARKERS):
        audit.warn(check, "Source contains identity-field labels; confirm they are blank and absent from every submitted file.")


def open_archive_names(path: Path, audit: Audit) -> list[str] | None:
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                return [name for name in archive.namelist() if not name.endswith("/")]
        except Exception as exc:
            audit.fail("support_archive", f"Cannot read ZIP archive: {exc}")
            return None
    try:
        import rarfile  # type: ignore

        with rarfile.RarFile(path) as archive:
            return [item.filename for item in archive.infolist() if not item.isdir()]
    except Exception as exc:
        audit.fail("support_archive", f"Cannot inspect RAR archive in this environment: {exc}")
        return None


def inspect_support_archive(
    path: Path | None,
    appendix_text: str,
    paper_text: str,
    audit: Audit,
) -> None:
    no_support = "本论文没有支撑材料" in compact(appendix_text)
    no_program = "本论文没有用到程序" in compact(appendix_text)

    if path is None:
        if no_support:
            audit.pass_("support_archive", "No archive supplied and the appendix contains the required no-support statement.")
        else:
            audit.fail("support_archive", "No ZIP/RAR supplied and the appendix does not state that there is no supporting material.")
        return

    if not path.exists():
        audit.fail("support_archive", f"Supporting-material archive does not exist: {path}")
        return
    if path.suffix.lower() not in {".zip", ".rar"}:
        audit.fail("support_archive", "Supporting material must be one ZIP or RAR file.")
        return
    if path.stat().st_size > MAX_BYTES:
        audit.fail("support_archive", f"Supporting-material archive exceeds 20 MB: {path.stat().st_size} bytes.")
    else:
        audit.pass_("support_archive_size", f"Archive size is within 20 MB: {path.stat().st_size} bytes.")

    names = open_archive_names(path, audit)
    if names is None:
        return
    if not names:
        audit.fail("support_archive", "Supporting-material archive is empty.")
        return

    lowered_names = [name.lower() for name in names]
    for name in names:
        if any(marker.lower() in name.lower() for marker in IDENTITY_MARKERS + FRONT_MATTER_MARKERS):
            audit.fail("support_anonymity", f"Forbidden identity/front-matter marker in archive name: {name}")

    code_files = [name for name in names if Path(name).suffix.lower() in CODE_SUFFIXES]
    if not no_program and not code_files:
        audit.fail("support_code", "Archive contains no recognizable source-code or software-command file.")
    elif code_files:
        audit.pass_("support_code", f"Archive contains {len(code_files)} recognizable code/data-command files.")

    appendix_compact = compact(appendix_text).lower()
    missing_from_list = []
    for name in names:
        basename = Path(name).name.lower()
        if basename and compact(basename) not in appendix_compact:
            missing_from_list.append(name)
    if missing_from_list:
        preview = ", ".join(missing_from_list[:8])
        audit.fail(
            "support_inventory",
            f"Archive files are not listed verbatim in the appendix ({len(missing_from_list)}): {preview}",
        )
    else:
        audit.pass_("support_inventory", "Every archive file name appears in the appendix inventory.")

    suspicious_raw = [name for name in names if re.search(r"(?:^|/)(?:附件|attachment)[-_ ]*\d", name, re.I)]
    if suspicious_raw:
        audit.warn(
            "problem_raw_data",
            "Possible problem-provided raw attachments are present; confirm they are not redundantly packaged: "
            + ", ".join(suspicious_raw[:8]),
        )

    if "使用了ai工具" in compact(paper_text).lower():
        ai_files = [name for name in lowered_names if ("ai" in name or "人工智能" in name) and name.endswith(".pdf")]
        if not ai_files:
            audit.fail("ai_disclosure", "Paper declares AI use but no recognizable AI-use-details PDF is in the archive.")
        else:
            audit.pass_("ai_disclosure", "AI-use-details PDF found in supporting material.")


def within_a4(width: float, height: float) -> bool:
    normal = abs(width - A4_WIDTH_PT) <= A4_TOLERANCE_PT and abs(height - A4_HEIGHT_PT) <= A4_TOLERANCE_PT
    rotated = abs(height - A4_WIDTH_PT) <= A4_TOLERANCE_PT and abs(width - A4_HEIGHT_PT) <= A4_TOLERANCE_PT
    return normal or rotated


def inspect_layout_with_pdfplumber(pdf_path: Path, audit: Audit) -> None:
    try:
        import pdfplumber  # type: ignore
    except Exception as exc:
        audit.fail("layout", f"pdfplumber unavailable; margins and footer page numbers are UNVERIFIED: {exc}")
        return

    margin_violations: list[str] = []
    footer_failures: list[int] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                width, height = float(page.width), float(page.height)
                words = page.extract_words() or []
                expected = str(page_index)
                footer_words = [
                    word for word in words
                    if word.get("text", "").strip() == expected
                    and float(word.get("top", 0)) >= height * 0.86
                    and abs((float(word.get("x0", 0)) + float(word.get("x1", 0))) / 2 - width / 2) <= width * 0.12
                ]
                if not footer_words:
                    footer_failures.append(page_index)

                for word in words:
                    if word in footer_words:
                        continue
                    x0 = float(word.get("x0", 0))
                    x1 = float(word.get("x1", width))
                    top = float(word.get("top", 0))
                    bottom = float(word.get("bottom", height))
                    if (
                        x0 < MARGIN_PT - MARGIN_TOLERANCE_PT
                        or x1 > width - MARGIN_PT + MARGIN_TOLERANCE_PT
                        or top < MARGIN_PT - MARGIN_TOLERANCE_PT
                        or bottom > height - MARGIN_PT + MARGIN_TOLERANCE_PT
                    ):
                        margin_violations.append(f"page {page_index}: text '{word.get('text', '')[:24]}'")
                        break

                for image in page.images or []:
                    x0 = float(image.get("x0", 0))
                    x1 = float(image.get("x1", width))
                    top = float(image.get("top", 0))
                    bottom = float(image.get("bottom", height))
                    if (
                        x0 < MARGIN_PT - MARGIN_TOLERANCE_PT
                        or x1 > width - MARGIN_PT + MARGIN_TOLERANCE_PT
                        or top < MARGIN_PT - MARGIN_TOLERANCE_PT
                        or bottom > height - MARGIN_PT + MARGIN_TOLERANCE_PT
                    ):
                        margin_violations.append(f"page {page_index}: raster image crosses 2.5 cm content boundary")
                        break
    except Exception as exc:
        audit.fail("layout", f"Cannot inspect PDF layout: {exc}")
        return

    if footer_failures:
        audit.fail("page_numbers", "Missing expected centered footer page numbers on pages: " + ", ".join(map(str, footer_failures)))
    else:
        audit.pass_("page_numbers", "Arabic page numbers start at 1 and continue in the centered footer.")

    if margin_violations:
        audit.fail("margins", "Content crosses the 2.5 cm boundary: " + "; ".join(margin_violations[:8]))
    else:
        audit.pass_("margins", "Text and raster images stay within the 2.5 cm content boundary; verify vector graphics visually.")


def inspect_pdf(pdf_path: Path, source: Path | None, support: Path | None, audit: Audit) -> None:
    if not pdf_path.exists():
        audit.fail("pdf", f"PDF does not exist: {pdf_path}")
        return
    if pdf_path.suffix.lower() != ".pdf":
        audit.fail("pdf", "Electronic paper must be a single PDF or Word file; this checker accepts PDF only.")
        return
    if pdf_path.stat().st_size > MAX_BYTES:
        audit.fail("pdf_size", f"Paper PDF exceeds 20 MB: {pdf_path.stat().st_size} bytes.")
    else:
        audit.pass_("pdf_size", f"Paper PDF is within 20 MB: {pdf_path.stat().st_size} bytes.")

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        audit.fail("pdf", f"Cannot open PDF: {exc}")
        return
    if not reader.pages:
        audit.fail("pdf", "PDF has no pages.")
        return

    bad_page_sizes = []
    page_texts = []
    for index, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if not within_a4(width, height):
            bad_page_sizes.append(f"{index} ({width:.1f} x {height:.1f} pt)")
        try:
            page_texts.append(page.extract_text() or "")
        except Exception:
            page_texts.append("")
    if bad_page_sizes:
        audit.fail("a4", "Non-A4 pages: " + ", ".join(bad_page_sizes))
    else:
        audit.pass_("a4", f"All {len(reader.pages)} pages are A4.")

    first = compact(page_texts[0])
    if "摘要" not in first:
        audit.fail("first_page", "First electronic page does not contain an abstract heading.")
    if "关键词" not in first and "关键字" not in first:
        audit.fail("first_page", "First electronic page does not contain keywords.")
    if any(marker in first for marker in FRONT_MATTER_MARKERS):
        audit.fail("first_page", "Electronic paper contains a commitment/numbering-page marker on page 1.")
    if "摘要" in first and ("关键词" in first or "关键字" in first) and not any(marker in first for marker in FRONT_MATTER_MARKERS):
        audit.pass_("first_page", "Page 1 contains title/abstract/keywords structure and no paper-only front matter marker.")

    if len(page_texts) > 1:
        second_top = "".join(normalized_lines(page_texts[1])[:12])
        if "关键词" in second_top or "关键字" in second_top:
            audit.fail("abstract_length", "Keywords spill onto page 2; title, abstract and keywords must fit on page 1.")
        else:
            audit.pass_("abstract_length", "Keywords end on page 1; no page-2 spill detected.")

    toc_pages = [
        str(index + 1) for index, text in enumerate(page_texts[:5])
        if has_standalone_heading(text, "目录")
    ]
    if toc_pages:
        audit.fail("toc", "Table of contents found on PDF page(s): " + ", ".join(toc_pages))
    else:
        audit.pass_("toc", "No standalone table-of-contents heading found in the first five pages.")

    paper_text = "\n".join(page_texts)
    if any(marker in compact(paper_text) for marker in IDENTITY_MARKERS):
        audit.fail("anonymity", "Paper contains explicit contestant/school/region identity-field markers.")
    else:
        audit.pass_("anonymity", "No explicit identity-field marker found; names, metadata and images still require review.")

    metadata = reader.metadata or {}
    author = str(metadata.get("/Author", "") or "").strip()
    if author and author.lower() not in {"anonymous", "匿名", "none"}:
        audit.fail("metadata", f"PDF Author metadata is not blank: {author!r}")
    else:
        audit.pass_("metadata", "PDF Author metadata is blank or anonymous.")

    appendix_index = find_appendix_page(page_texts)
    appendix_text = ""
    if appendix_index is None:
        audit.fail("appendix", "No appendix heading found after the body.")
    else:
        body_pages = max(0, appendix_index - 1)
        appendix_text = "\n".join(page_texts[appendix_index:])
        if 25 <= body_pages <= 28:
            audit.pass_("body_pages", f"Body and references have {body_pages} pages, within the user-required 25-28 range.")
        else:
            audit.fail("body_pages", f"Body and references have {body_pages} pages; the user-required range is 25-28, excluding abstract and appendix.")

        appendix_compact = compact(appendix_text)
        if "支撑材料" not in appendix_compact:
            audit.fail("appendix_inventory", "Appendix does not contain a supporting-material file list or no-support statement.")
        else:
            audit.pass_("appendix_inventory", "Appendix contains supporting-material inventory text.")

        no_program = "本论文没有用到程序" in appendix_compact
        code_like = any(re.search(pattern, appendix_text, re.I) for pattern in CODE_PATTERNS)
        if no_program:
            audit.pass_("appendix_code", "Appendix contains the required no-program statement.")
        elif code_like:
            audit.pass_("appendix_code", "Appendix contains recognizable source-code text; completeness still requires source comparison.")
        else:
            audit.fail("appendix_code", "Appendix has neither recognizable full source code nor the required no-program statement.")

    if "参考文献" not in compact(paper_text):
        audit.warn("references", "No reference-list heading detected; confirm that no public or third-party material was used.")
    else:
        audit.pass_("references", "Reference-list heading detected; perform citation-to-entry bidirectional review separately.")

    inspect_layout_with_pdfplumber(pdf_path, audit)
    if source is not None:
        inspect_source(source, audit)
    inspect_support_archive(support, appendix_text, paper_text, audit)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path, help="Final electronic paper PDF")
    parser.add_argument("--source", type=Path, help="Main .tex or .typ source")
    parser.add_argument("--support-archive", type=Path, help="Final supporting-material ZIP/RAR")
    parser.add_argument("--report", type=Path, help="Optional JSON audit output")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    audit = Audit()
    inspect_pdf(args.pdf, args.source, args.support_archive, audit)
    result = {
        "status": "FAIL" if audit.failed else "PASS",
        "pdf": str(args.pdf),
        "pdf_sha256": sha256(args.pdf),
        "source": str(args.source) if args.source else None,
        "source_sha256": sha256(args.source),
        "support_archive": str(args.support_archive) if args.support_archive else None,
        "support_archive_sha256": sha256(args.support_archive),
        "findings": [asdict(item) for item in audit.findings],
    }
    for item in audit.findings:
        print(f"{item.level}: {item.check}: {item.message}")
    print(f"RESULT: {result['status']}")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if audit.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
