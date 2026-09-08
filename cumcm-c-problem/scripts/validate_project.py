#!/usr/bin/env python3
from __future__ import annotations
import argparse
import re
import shutil
import subprocess
from pathlib import Path

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


def emit(level: str, msg: str) -> None:
    print(f"[{level}] {msg}")


def run(cmd, cwd: Path):
    return subprocess.run(cmd, cwd=str(cwd), text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def keyword_count(tex: str):
    m = re.search(r"\\keywords\s*\{([^}]*)\}", tex, re.S)
    if not m:
        return None
    s = m.group(1).strip()
    parts = re.split(r"\\quad|[，,；;]+", s)
    return len([x for x in parts if x.strip()])


def page_text(pdf: Path, page: int):
    if not shutil.which("pdftotext"):
        return None
    r = subprocess.run(["pdftotext", "-enc", "UTF-8", "-f", str(page), "-l", str(page), "-layout", str(pdf), "-"], text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return r.stdout if r.returncode == 0 else None


def pdf_pages(pdf: Path):
    if not shutil.which("pdfinfo"):
        return None
    r = subprocess.run(["pdfinfo", str(pdf)], text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return None
    m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
    return int(m.group(1)) if m else None


def body_page_count(total: int, appendix_page: int | None) -> int:
    """Page 1 is the separate abstract; appendix_page is a 1-based physical page."""
    return max(0, (appendix_page - 2) if appendix_page is not None else (total - 1))


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit CUMCM C-problem project structure and PDF presentation.")
    ap.add_argument("project")
    ap.add_argument("--compile", action="store_true", help="Compile with XeLaTeX before PDF checks")
    ap.add_argument("--min-pages", type=int, default=25, choices=[25], help="User-required body-page minimum, fixed at 25")
    ap.add_argument("--max-pages", type=int, default=28, choices=[28], help="User-required body-page maximum, fixed at 28")
    ap.add_argument("--max-keywords", type=int, default=None, help="Only set when the applicable rules or user explicitly require a limit")
    ap.add_argument("--appendix-start-page", type=int, help="Verified 1-based physical PDF page where the appendix starts")
    args = ap.parse_args()
    if args.max_pages < 1 or (args.min_pages is not None and not 1 <= args.min_pages <= args.max_pages):
        ap.error("page limits must be positive and min-pages cannot exceed max-pages")
    if args.max_keywords is not None and args.max_keywords < 1:
        ap.error("max-keywords must be positive")
    if args.appendix_start_page is not None and args.appendix_start_page < 3:
        ap.error("appendix-start-page must follow the abstract and body")

    root = Path(args.project).resolve()
    texfile = root / "example.tex"
    failures = 0

    for name in ["figures", "code"]:
        p = root / name
        if p.is_dir(): emit(PASS, f"{name}/ exists")
        else: emit(FAIL, f"missing {name}/"); failures += 1

    if not texfile.exists():
        emit(FAIL, "missing example.tex")
        return 2
    tex = texfile.read_text(encoding="utf-8", errors="ignore")

    checks = [
        (r"\\documentclass(?:\[[^]]*\])?\{cumcmthesis\}", "uses cumcmthesis class"),
        (r"\\tihao\{C\}", "problem type is C"),
        (r"\\begin\{abstract\}", "abstract exists"),
        (r"\\keywords\{", "keywords exist"),
        (r"\\section\{问题重述\}", "problem restatement section exists"),
        (r"\\section\{问题分析\}", "problem analysis section exists"),
        (r"\\section\{模型假设\}", "assumptions section exists"),
        (r"\\section\{符号说明\}", "symbol section exists"),
        (r"\\begin\{thebibliography\}", "references exist"),
    ]
    for pat, msg in checks:
        if re.search(pat, tex, re.S): emit(PASS, msg)
        else: emit(FAIL, msg); failures += 1

    if "\\tableofcontents" in re.sub(r"(?m)^\s*%.*$", "", tex):
        emit(FAIL, "table of contents is enabled")
        failures += 1
    else:
        emit(PASS, "no table of contents")

    nkw = keyword_count(tex)
    if nkw is None:
        pass
    elif args.max_keywords is None or nkw <= args.max_keywords:
        emit(PASS, f"keyword count = {nkw}; no implicit keyword limit")
    else:
        emit(FAIL, f"keyword count = {nkw} (explicit limit {args.max_keywords})")
        failures += 1

    abs_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    if abs_match:
        if "\\textbf{" in abs_match.group(1):
            emit(PASS, "abstract highlights at least one key model/result with bold")
        else:
            emit(WARN, "abstract has no \\textbf{} highlight")

    if re.search(r"\\end\{abstract\}\s*\\newpage", tex, re.S):
        emit(PASS, "explicit new page after abstract")
    else:
        emit(WARN, "consider \\newpage after abstract to lock problem restatement to page 2")

    has_optimization = bool(re.search(r"\\(?:min|max)|\\text\{s\.t\.\}|\\mathrm\{s\.t\.\}", tex))
    has_summary_model = "\\boxed{" in tex and "\\left\\{" in tex
    if has_optimization and not has_summary_model:
        emit(WARN, "optimization detected but no boxed brace model summary found")
    elif has_summary_model:
        emit(PASS, "boxed model-summary form detected")

    includegraphics = re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", tex)
    emit(PASS, f"figure references in TeX: {len(includegraphics)}")
    captions = len(re.findall(r"\\caption(?:\[[^]]*\])?\{", tex))
    emit(PASS, f"captions in TeX: {captions}")

    if args.compile:
        if not shutil.which("xelatex"):
            emit(FAIL, "xelatex not installed; requested compilation could not run")
            failures += 1
        elif not (root / "cumcmthesis.cls").exists() and not shutil.which("kpsewhich"):
            emit(FAIL, "cumcmthesis.cls not found locally and TeX lookup is unavailable")
            failures += 1
        else:
            ok = True
            for _ in range(2):
                r = run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "example.tex"], root)
                if r.returncode != 0:
                    emit(FAIL, "XeLaTeX compile failed")
                    print(r.stdout[-3000:])
                    failures += 1
                    ok = False
                    break
            if ok: emit(PASS, "XeLaTeX compiled twice")

    pdf = root / "example.pdf"
    if pdf.exists():
        p1 = page_text(pdf, 1)
        p2 = page_text(pdf, 2)
        if p1 is None or p2 is None:
            emit(FAIL, "PDF text checks could not run; install Poppler or use the shared format audit")
            failures += 1
        if p1 is not None:
            if "关键词" in p1 or "关键字" in p1:
                emit(PASS, "keywords appear on page 1")
            else:
                emit(FAIL, "could not confirm keywords on page 1; inspect the rendered PDF")
                failures += 1
            if "问题重述" in p1:
                emit(FAIL, "problem restatement appears on page 1; abstract page is not isolated")
                failures += 1
            else:
                emit(PASS, "problem restatement does not spill onto page 1")
        if p2 is not None:
            if "问题重述" in p2: emit(PASS, "problem restatement starts by page 2")
            else: emit(FAIL, "problem restatement not found on page 2; inspect the rendered PDF"); failures += 1

        total = pdf_pages(pdf)
        if total:
            appendix_page = args.appendix_start_page
            if appendix_page is not None and appendix_page > total:
                emit(FAIL, "appendix-start-page exceeds the PDF page count")
                failures += 1
                appendix_page = None
            if appendix_page is None and shutil.which("pdftotext"):
                for i in range(1, total + 1):
                    txt = page_text(pdf, i) or ""
                    # Only a heading near the top counts; prose mentioning an appendix does not.
                    head = "\n".join(line for line in txt.splitlines() if line.strip()).splitlines()[:5]
                    if any(re.match(r"^\s*(?:附\s*录(?:\s*[A-Z一二三四五六七八九十0-9]+)?(?:\s+.*)?|Appendix(?:\s+.*)?)\s*$", line, re.I) for line in head):
                        appendix_page = i
                        break
            main_pages = body_page_count(total, appendix_page)
            if main_pages <= args.max_pages:
                emit(PASS, f"estimated body pages = {main_pages} (limit {args.max_pages}; excludes abstract and appendix)")
            else:
                emit(FAIL, f"estimated body pages = {main_pages}; exceeds limit {args.max_pages}; verify appendix start")
                failures += 1
            if args.min_pages is not None and main_pages < args.min_pages:
                emit(FAIL, f"body pages below user-required minimum {args.min_pages}; do not pad the paper")
                failures += 1
        else:
            emit(FAIL, "PDF page count unavailable; page-limit check is unverified")
            failures += 1
    else:
        emit(FAIL, "missing example.pdf; PDF presentation is unverified")
        failures += 1

    log = root / "example.log"
    if log.exists():
        s = log.read_text(encoding="utf-8", errors="ignore")
        if "Overfull \\hbox" in s: emit(WARN, "Overfull \\hbox found")
        else: emit(PASS, "no Overfull \\hbox found")
        if re.search(r"undefined references|Reference .* undefined", s, re.I): emit(FAIL, "undefined references found"); failures += 1
        else: emit(PASS, "no undefined-reference warning found")

    if (root / "code").is_dir():
        files = [p for p in (root / "code").rglob("*") if p.is_file()]
        if files: emit(PASS, f"code/ contains {len(files)} file(s)")
        else: emit(WARN, "code/ is empty; final delivery should include complete runnable code")

    emit(WARN, "This skeleton checker is not full format or scientific acceptance; use the shared format checker and visual review.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
