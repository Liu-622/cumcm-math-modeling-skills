#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

exit_code = 0

def fail(msg):
    global exit_code
    print(f"FAIL: {msg}")
    exit_code = 1

def warn(msg):
    print(f"WARN: {msg}")

def info(msg):
    print(f"INFO: {msg}")


def parse_args():
    parser = argparse.ArgumentParser(description="Cross-platform Typst/LaTeX writing text gate (not a PDF or mathematical audit).")
    parser.add_argument("paper", nargs="?", help="Paper directory")
    for option in ("paper-dir", "root-dir", "main", "sections-dir", "references", "figures-dir", "results-file", "problem-analysis", "all-results"):
        parser.add_argument("--" + option, type=Path)
    parser.add_argument("--internal-term", action="append", default=[])
    parser.add_argument("--no-internal-check", action="store_true")
    return parser.parse_args()

args = parse_args()
if args.main is not None and args.paper_dir is None and args.paper is None:
    paper = args.main.parent
else:
    paper = args.paper_dir or (Path(args.paper) if args.paper else (Path(".") if any(Path(x).is_file() for x in ("main.typ", "main.tex")) else Path("paper")))
root = args.root_dir or (paper if paper == Path(".") else paper.resolve().parent)
main_candidates = [paper / "main.typ", paper / "main.tex"]
if args.main is None and all(path.is_file() for path in main_candidates):
    print("ERROR: Both main.typ and main.tex exist; pass --main for the selected engine.", file=sys.stderr)
    raise SystemExit(2)
if args.main is not None:
    main = args.main if args.main.is_absolute() or args.paper_dir is None else paper / args.main
else:
    main = next((path for path in main_candidates if path.is_file()), paper / "main.typ")
sections_dir = args.sections_dir or (paper / "sections" if (paper / "sections").is_dir() else None)
refs = args.references or next((paper / name for name in ("references.typ", "references.tex") if (paper / name).is_file()), None)
figures_dir = args.figures_dir or (root / "figures" if (root / "figures").is_dir() else None)
results_file = args.results_file or next((root / name for name in ("reports/RESULTS_REPORT.md", "RESULTS_REPORT.md", "RESULTS_REPORT") if (root / name).is_file()), None)
problem_analysis = args.problem_analysis or next((root / name for name in ("reports/ANALYSIS_MODELING_REPORT.md", "ANALYSIS_MODELING_REPORT.md", "PROBLEM_ANALYSIS.md") if (root / name).is_file()), None)
all_results = args.all_results or next((root / name for name in ("results/all_results.json", "figures/all_results.json") if (root / name).is_file()), None)
no_internal_check = args.no_internal_check
extra_internal_terms = args.internal_term

def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")

def rel(path):
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)

def extract_calls(text, name):
    calls = []
    pattern = re.compile(r"#" + re.escape(name) + r"\s*\(")
    for match in pattern.finditer(text):
        open_pos = text.find("(", match.start())
        depth = 0
        in_string = False
        escape = False
        for idx in range(open_pos, len(text)):
            ch = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    calls.append((match.start(), idx + 1, text[open_pos + 1:idx]))
                    break
    return calls

def remove_spans(text, spans):
    if not spans:
        return text
    parts = []
    last = 0
    for start, end, _ in spans:
        parts.append(text[last:start])
        last = end
    parts.append(text[last:])
    return "".join(parts)

def unique_paths(paths):
    seen = set()
    out = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            out.append(path)
            seen.add(key)
    return out

def section_sort_key(path):
    match = re.match(r"^(\d+)[_-](.*)$", path.name)
    if match:
        return (0, int(match.group(1)), match.group(2))
    return (1, path.name)

info(f"paper dir: {paper}")
info(f"root dir: {root}")
info(f"main file: {main}")
if sections_dir:
    info(f"sections dir: {sections_dir}")
if figures_dir:
    info(f"figures dir: {figures_dir}")
if results_file:
    info(f"results file: {results_file}")

if not paper.exists():
    fail(f"paper directory not found: {paper}")

if not main.is_file():
    fail(f"missing main paper file: {main}")
    sys.exit(exit_code)

# Detect engine by main file extension
if main.suffix.lower() not in {".tex", ".typ"}:
    fail(f"unsupported main file extension: {main.suffix}")
    sys.exit(exit_code)
is_latex = main.suffix.lower() == ".tex"
is_typst = main.suffix.lower() == ".typ"
engine_name = "LaTeX" if is_latex else "Typst"
info(f"detected engine: {engine_name} (main suffix: {main.suffix})")

def active_text(text):
    if is_latex:
        return re.sub(r"(?m)(?<!\\)%.*$", "", text)
    # Ignore full-line Typst comments without damaging URLs in strings.
    return re.sub(r"(?m)^\s*//[^\n]*$", "", text)

main_text = active_text(read(main))

# Section file extension matches engine
section_ext = "*.tex" if is_latex else "*.typ"
if sections_dir and sections_dir.exists():
    section_files = sorted(sections_dir.glob(section_ext), key=section_sort_key)
elif paper.exists():
    excluded = {main.resolve()}
    if refs:
        excluded.add(refs.resolve())
    section_files = [
        path for path in sorted(paper.rglob(section_ext), key=section_sort_key)
        if path.resolve() not in excluded
    ]
    if section_files:
        warn(f"sections dir not supplied/found; using other {section_ext} files under paper dir as body sections")
else:
    section_files = []

info(f"section file count: {len(section_files)}")
if not section_files:
    warn(f"no separate section {section_ext} files detected; treating paper as a single-file {engine_name} document")

# Include/input detection: Typst uses #include("..."), LaTeX uses \input{...} or \include{...}
if is_typst:
    include_re = re.compile(r'#include\s*(?:\(\s*)?"([^"]+\.typ)"')
    includes = include_re.findall(main_text)
else:
    include_re = re.compile(r'\\(?:input|include)\s*\{([^}]+)\}')
    raw_includes = [inc.strip() for inc in include_re.findall(main_text)]
    # LaTeX \input{name} may omit .tex extension; normalize by appending .tex if missing
    includes = [inc if inc.endswith(".tex") else inc + ".tex" for inc in raw_includes]
include_paths = [(main.parent / inc).resolve() for inc in includes]
include_names = [Path(inc).name for inc in includes]

info(f"main include count: {len(includes)}")
seen = set()
for name in include_names:
    if name in seen:
        fail(f"duplicate {engine_name} include: {name}")
    seen.add(name)

for inc, path in zip(includes, include_paths):
    if not path.exists():
        fail(f"included {engine_name} file does not exist: {inc}")

actual_names = [path.name for path in section_files]
if includes:
    included_set = set(include_names)
    for name in actual_names:
        if name not in included_set and not name.startswith("A_"):
            warn(f"body section file not included by main: {name}")
else:
    warn(f"main has no include/input calls; skip include order checks")

def leading_number(name):
    match = re.match(r"^(\d+)[_-]", name)
    return int(match.group(1)) if match else None

numbers = [leading_number(name) for name in include_names if leading_number(name) is not None]
if numbers and numbers != sorted(numbers):
    warn(f"section filenames are not ascending; verify actual semantic order: {numbers}")
if numbers:
    expected = list(range(min(numbers), max(numbers) + 1))
    missing = [num for num in expected if num not in numbers]
    if missing:
        warn(f"numbered section sequence has gaps: {missing}")

if problem_analysis and problem_analysis.exists():
    pa = read(problem_analysis)
    problem_hits = re.findall(r"(?:子问题|问题)\s*[一二三四五六七八九十0-9]+", pa)
    declared = re.search(r"共\s*(\d+)\s*个子问题", pa)
    expected_problem_count = int(declared.group(1)) if declared else len(set(problem_hits))
    paper_problem_sections = [name for name in include_names or actual_names if re.search(r"problem|问题|q\d", name, re.I)]
    if expected_problem_count and paper_problem_sections and len(paper_problem_sections) < expected_problem_count:
        warn(
            "paper problem sections may be fewer than analysis subproblems: "
            f"paper={len(paper_problem_sections)}, analysis={expected_problem_count}"
        )
else:
    info("problem analysis file not supplied/found; skip subproblem count check")

placeholder_re = re.compile(r"PLACEHOLDER|TODO|TBD|XXX|待补充|待续写|这里补|示例数据|待完善")
default_internal_terms = [
    "RESULTS_REPORT",
    "ANALYSIS_MODELING_REPORT.md",
    "PROBLEM_ANALYSIS.md",
    "CLAUDE.md",
    "figures/*.json",
    "_tmp/",
]
internal_terms = default_internal_terms + extra_internal_terms
if results_file:
    internal_terms.append(results_file.name)
if problem_analysis:
    internal_terms.append(problem_analysis.name)
if all_results:
    internal_terms.append(all_results.name)
internal_terms = sorted(set(term for term in internal_terms if term))
internal_re = re.compile("|".join(re.escape(term) for term in internal_terms)) if internal_terms else None

typ_files = unique_paths([main] + section_files + ([refs] if refs and refs.exists() else []) + sorted(paper.glob(section_ext)))
file_texts = []
combined = []
section_titles = []

for path in typ_files:
    if not path.exists():
        continue
    text = active_text(read(path))
    file_texts.append((path, text))
    combined.append(text)
    path_rel = rel(path)

    if placeholder_re.search(text):
        fail(f"placeholder text remains in {path_rel}")

    is_appendix = path.name.startswith("A_") or "appendix" in path.name.lower()
    if not no_internal_check and internal_re and internal_re.search(text):
        if is_appendix:
            warn(f"internal workflow term appears in appendix: {path_rel}")
        else:
            fail(f"internal workflow term leaked into paper text: {path_rel}")

    if path in section_files:
        body = text.strip()
        info(f"section length: {path.name} {len(body)} chars")
        if len(body) < 800 and not path.name.startswith("A_"):
            warn(f"section is short: {path.name} ({len(body)} chars)")

        # Auxiliary sections (appendix code, abstracts, appendices) may
        # legitimately omit a level-1 heading because the title is rendered
        # by main.typ/main.tex directly.
        lower_name = path.name.lower()
        is_aux_section = (
            path.name.startswith("A_")
            or lower_name.startswith("abstract")
            or lower_name.startswith("appendices")
        )

        if is_typst:
            # Typst heading check: `= Title` (space after =)
            malformed_headings = [
                line.strip()
                for line in text.splitlines()
                if re.match(r"^={1,6}(?![=\s]).+", line)
            ]
            for line in malformed_headings[:5]:
                fail(f"Typst heading is missing a space after '=' in {path.name}: {line[:80]}")
            heading = re.search(r"(?m)^=\s+.+", text)
            if not heading and not is_aux_section:
                warn(f"section has no literal level-1 Typst heading; check whether main or a helper generates it: {path.name}")
            if heading:
                title = heading.group(0).lstrip("= ").strip()
                section_titles.append((path.name, title))
                if re.search(r"problem\d+|q\d", path.name, re.I) and not re.search(r"问题|Problem|Question", title, re.I):
                    warn(f"problem section title may not match filename: {path.name} -> {title}")
            if re.search(r"(?m)^={3,}\s+", text):
                warn(f"deep heading level appears in section: {path.name}")
            list_count = len(re.findall(r"#(?:enum|list)\s*\(", text))
            if list_count >= 3:
                warn(f"many lists in section, consider prose: {path.name} ({list_count})")
            figure_calls = extract_calls(text, "figure")
            text_without_figures = remove_spans(text, figure_calls)
            if len(figure_calls) >= 2 and len(text_without_figures.strip()) < 1000:
                warn(f"many figures but little surrounding prose: {path.name}")
        else:
            # LaTeX heading check: \section{...}
            section_headings = re.findall(r"\\section\*?\s*\{([^}]*)\}", text)
            subsection_headings = re.findall(r"\\subsection\*?\s*\{([^}]*)\}", text)
            if not section_headings and not subsection_headings and not is_aux_section:
                warn(f"section has no literal heading; check whether main generates it: {path.name}")
            for title in section_headings:
                section_titles.append((path.name, title))
                if re.search(r"problem\d+|q\d", path.name, re.I) and not re.search(r"问题|Problem|Question", title, re.I):
                    warn(f"problem section title may not match filename: {path.name} -> {title}")
            list_count = len(re.findall(r"\\begin\{(?:itemize|enumerate)\}", text))
            if list_count >= 3:
                warn(f"many lists in section, consider prose: {path.name} ({list_count})")
            figure_env_count = len(re.findall(r"\\begin\{figure\}", text))
            if figure_env_count >= 2 and len(text) < 2000:
                warn(f"many figures but little surrounding prose: {path.name}")

paper_text = "\n".join(combined)

if section_titles:
    info("section title order:")
    for idx, (name, title) in enumerate(section_titles, 1):
        info(f"  {idx}. {name} -> {title}")
    titles = [title for _, title in section_titles]
    if len(titles) != len(set(titles)):
        fail("duplicate level-1 section titles detected")

# Image reference check: Typst uses image("..."), LaTeX uses \includegraphics{...}
if is_typst:
    image_re = re.compile(r'image\(\s*"([^"]+)"')
else:
    image_re = re.compile(r'\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}')
graphic_dirs = []
if is_latex:
    for block in re.findall(r"\\graphicspath\s*\{((?:\s*\{[^}]*\}\s*)+)\}", paper_text):
        graphic_dirs.extend(main.parent / value for value in re.findall(r"\{([^}]*)\}", block))
for path, text in file_texts:
    for ref in image_re.findall(text):
        if is_latex and re.search(r"[\\#]", ref):
            warn(f"dynamic LaTeX image path requires compiler verification in {rel(path)}: {ref}")
            continue
        bases = [path.parent] if is_typst else [main.parent] + graphic_dirs
        candidates = [base / ref for base in bases]
        if is_latex and not Path(ref).suffix:
            candidates += [candidate.with_suffix(ext) for candidate in list(candidates) for ext in (".pdf", ".png", ".jpg", ".jpeg", ".eps")]
        if not any(target.is_file() for target in candidates):
            fail(f"referenced image does not exist from {rel(path)}: {ref}")

if figures_dir and figures_dir.exists():
    for fig in sorted(figures_dir.glob("*.pdf")):
        if fig.name not in paper_text:
            warn(f"figure PDF not referenced in paper: {fig.name}")
else:
    info("figures dir not supplied/found; skip unused figure check")

# Figure caption check
if is_typst:
    for _, _, body in extract_calls(paper_text, "figure"):
        if "caption:" not in body:
            fail("figure without caption")
            continue
        cap_match = re.search(r"caption:\s*\[(.*?)\]", body, re.S)
        if cap_match:
            cap = re.sub(r"\s+", " ", cap_match.group(1)).strip()
            if len(cap) > 80:
                warn(f"long figure caption: {cap[:80]}...")
            if len(cap) < 4:
                warn("very short figure caption")
else:
    # LaTeX: check \begin{figure}...\end{figure} blocks contain \caption{}
    figure_blocks = re.findall(r"\\begin\{figure\}.*?\\end\{figure\}", paper_text, re.S)
    for block in figure_blocks:
        cap_match = re.search(r"\\caption\{([^}]*)\}", block)
        if not cap_match:
            fail("LaTeX figure without \\caption{}")
            continue
        cap = re.sub(r"\s+", " ", cap_match.group(1)).strip()
        if len(cap) > 80:
            warn(f"long figure caption: {cap[:80]}...")
        if len(cap) < 4:
            warn("very short figure caption")

if refs and refs.exists():
    refs_text = read(refs)
    if len(refs_text.strip()) < 80:
        warn(f"{rel(refs)} looks very short")
    if is_typst:
        citation_re = r"@\w[\w:-]*|#cite\("
    else:
        citation_re = r"\\cite\w*\{[^}]+\}"
    if re.search(citation_re, paper_text):
        info("citation markers detected")
    else:
        warn(f"{rel(refs)} exists but no citation markers detected in paper")
else:
    warn("references file not supplied/found; skip reference completeness check")

if results_file and results_file.exists():
    results_text = read(results_file)
    metric_names = re.findall(
        r"(?i)\b(?:rmse|mae|mape|r2|score|objective|accuracy|precision|recall|f1|"
        r"权重|目标值|误差|得分)\b",
        results_text,
    )
    if metric_names and not any(name.lower() in paper_text.lower() for name in metric_names[:20]):
        warn("metrics appear in result file but are hard to find in paper text")
else:
    info("results file not supplied/found; skip metric consistency scan")

if all_results and all_results.exists():
    try:
        data = json.loads(read(all_results))
        nums = []

        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                nums.append(value)

        walk(data)
        key_nums = []
        for num in nums[:100]:
            if abs(num) >= 1:
                key_nums.append(f"{num:.4f}".rstrip("0").rstrip("."))
        if key_nums and not any(num and num in paper_text for num in key_nums[:30]):
            warn("numeric values from all-results JSON are hard to find in paper")
    except Exception as exc:
        warn(f"cannot parse all-results JSON: {exc}")
else:
    info("all-results JSON not supplied/found; skip JSON numeric scan")

if exit_code == 0:
    print("PASS: writing text gate passed")
else:
    print("FAIL: writing text gate failed")

sys.exit(exit_code)
