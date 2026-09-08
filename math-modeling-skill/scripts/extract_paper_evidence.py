#!/usr/bin/env python3
"""Build compact evidence packets from the CUMCM paper archive.

Text mode scans every PDF with pypdf but emits only papers with >=500
non-whitespace characters. OCR mode emits the remaining papers after sampling
pages 1, 2, and about 70 percent with RapidOCR. Full paper text is never saved.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any

from pypdf import PdfReader


VERSION = "1.0.0"
SCHEMA = "math-modeling-paper-evidence-v1"
DEFAULT_ROOT = Path.cwd()
DEFAULT_INVENTORY = DEFAULT_ROOT / "_抓取清单.json"
DEFAULT_OUTPUT = Path.cwd() / "skill_build"

SECTION_TERMS = {
    "abstract": ["摘要", "关键词", "关键字"],
    "problem_analysis": ["问题重述", "问题分析", "题意分析", "问题一", "问题二", "问题三"],
    "assumptions": ["模型假设", "基本假设", "合理假设", "假设"],
    "data_processing": ["数据处理", "数据预处理", "缺失值", "异常值", "标准化", "归一化", "特征工程"],
    "modeling": ["模型建立", "模型构建", "建立模型", "目标函数", "约束条件", "数学模型"],
    "solution": ["模型求解", "算法流程", "求解过程", "算法设计", "参数估计"],
    "validation": ["敏感性分析", "稳健性分析", "误差分析", "模型检验", "对比实验", "残差分析"],
    "evaluation": ["模型评价", "模型优点", "模型缺点", "优缺点", "模型推广", "模型改进"],
    "innovation": ["创新点", "本文创新", "改进算法", "改进模型"],
    "conclusion": ["结果分析", "结论", "总结", "建议"],
}

MODEL_TERMS = [
    "线性规划", "整数规划", "0-1规划", "非线性规划", "多目标规划", "动态规划", "目标规划",
    "AHP", "层次分析", "熵权", "CRITIC", "TOPSIS", "PCA", "主成分分析", "因子分析",
    "模糊综合评价", "灰色关联", "DEA", "数据包络分析", "回归", "ARIMA", "指数平滑",
    "灰色预测", "GM(1,1)", "随机森林", "XGBoost", "LightGBM", "LSTM", "GRU", "SVM",
    "支持向量机", "KNN", "K-Means", "层次聚类", "DBSCAN", "GMM", "最短路径", "最大流",
    "最小费用流", "最小生成树", "TSP", "VRP", "微分方程", "SIR", "SEIR", "Logistic",
    "蒙特卡洛", "Monte Carlo", "离散事件仿真", "Agent-Based", "排队论", "马尔可夫", "博弈论",
]
ALGORITHM_TERMS = [
    "遗传算法", "模拟退火", "粒子群", "蚁群算法", "NSGA-II", "梯度下降", "最小二乘",
    "牛顿法", "单纯形法", "分支定界", "Dijkstra", "Floyd", "匈牙利算法", "贪心算法",
    "禁忌搜索", "网格搜索", "交叉验证", "Bootstrap", "L-M算法", "Levenberg-Marquardt",
]
VALIDATION_TERMS = [
    "敏感性分析", "稳健性分析", "鲁棒性", "误差分析", "残差分析", "对比实验", "模型检验",
    "交叉验证", "拟合优度", "R²", "R2", "RMSE", "MAE", "MAPE", "AIC", "BIC",
]
PROBLEM_TERMS = ["预测", "评价", "优化", "分类", "聚类", "路径", "调度", "网络", "仿真", "机理"]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def clean(text: str) -> str:
    text = (text or "").replace("\x00", "").replace("\r", "\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def atomic_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


def load_inventory(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records", [])
    return [r for r in records if r.get("status") == "success" and r.get("output_file")]


def parse_values(raw: list[str]) -> set[str]:
    out: set[str] = set()
    for value in raw:
        out.update(x.strip() for x in value.split(",") if x.strip())
    return out


def selected(record: dict[str, Any], years: set[str], ids: set[str]) -> bool:
    if years and str(record.get("year")) not in years:
        return False
    if not ids:
        return True
    fields = {str(record.get(k, "")).lower() for k in ("id", "paper_code")}
    return bool(fields & {x.lower() for x in ids})


def extract_pages(pdf: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    reader = PdfReader(str(pdf), strict=False)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            warnings.append(f"decrypt_failed: {exc}")
    pages: list[str] = []
    for number, page in enumerate(reader.pages, 1):
        try:
            pages.append(clean(page.extract_text() or ""))
        except Exception as exc:
            pages.append("")
            warnings.append(f"page_{number}_text_error: {exc}")
    return pages, warnings


def locate_pdftoppm() -> Path:
    explicit = os.environ.get("PDFTOPPM_EXE")
    candidates = [Path(explicit)] if explicit else []
    found = shutil.which("pdftoppm")
    if found:
        command = Path(found)
        candidates.append(command)
        if command.suffix.lower() in {".cmd", ".bat"} and len(command.parents) > 2:
            candidates.append(command.parents[2] / "native/poppler/Library/bin/pdftoppm.exe")
    for candidate in candidates:
        if candidate and candidate.exists() and candidate.suffix.lower() == ".exe":
            return candidate
    raise FileNotFoundError("pdftoppm.exe not found; set PDFTOPPM_EXE")


def sample_pages(page_count: int) -> dict[int, list[str]]:
    samples: dict[int, list[str]] = {}
    for page, reason in ((1, "first_page"), (2, "second_page"), (max(1, math.ceil(page_count * 0.70)), "seventy_percent")):
        if page <= page_count:
            samples.setdefault(page, []).append(reason)
    return samples


def ocr_page(pdf: Path, record_id: str, page: int, reasons: list[str], rendered: Path,
             engine: Any, pdftoppm: Path, dpi: int, fingerprint: str) -> dict[str, Any]:
    cache = rendered / f"{record_id}_p{page}.ocr.json"
    if cache.exists():
        try:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved.get("fingerprint") == fingerprint and saved.get("dpi") == dpi:
                saved["reasons"] = reasons
                return saved
        except Exception:
            pass
    rendered.mkdir(parents=True, exist_ok=True)
    prefix = rendered / f"{record_id}_p{page}"
    png = prefix.with_suffix(".png")
    started = time.perf_counter()
    subprocess.run(
        [str(pdftoppm), "-f", str(page), "-l", str(page), "-singlefile", "-r", str(dpi), "-png", str(pdf), str(prefix)],
        check=True, capture_output=True, timeout=180,
    )
    try:
        result = engine(png)
        lines = list(getattr(result, "txts", ()) or ())
        scores = [float(x) for x in (getattr(result, "scores", ()) or ())]
        item = {
            "page": page, "reasons": reasons, "text": clean("\n".join(lines))[:8000],
            "char_count": chars("".join(lines)), "line_count": len(lines),
            "mean_score": round(fmean(scores), 5) if scores else None,
            "seconds": round(time.perf_counter() - started, 3), "dpi": dpi,
            "fingerprint": fingerprint,
        }
        atomic_json(cache, item)
        return item
    finally:
        png.unlink(missing_ok=True)


def term_hits(pages: list[str], terms: list[str]) -> list[dict[str, Any]]:
    hits = []
    for term in terms:
        counts = [len(re.findall(re.escape(term), text, re.I)) for text in pages]
        if sum(counts):
            hits.append({"term": term, "count": sum(counts), "pages": [i + 1 for i, n in enumerate(counts) if n]})
    return sorted(hits, key=lambda x: (-x["count"], x["term"].lower()))


def excerpt(text: str, pos: int, limit: int = 520) -> str:
    start = max(0, pos - 80)
    end = min(len(text), pos + limit)
    left = max(text.rfind("\n", start, pos), text.rfind("。", start, pos))
    if left >= start:
        start = left + 1
    right_options = [x for x in (text.find("\n\n", pos, end), text.find("。", pos + 80, end)) if x >= 0]
    if right_options:
        end = min(right_options) + 1
    return clean(text[start:end])


def section_excerpts(pages: list[str]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for section, terms in SECTION_TERMS.items():
        items = []
        for page_no, text in enumerate(pages, 1):
            matched = [term for term in terms if term.lower() in text.lower()]
            if matched:
                pos = min(text.lower().find(term.lower()) for term in matched)
                items.append({"page": page_no, "matched_terms": matched, "text": excerpt(text, pos)})
            if len(items) >= 3:
                break
        result[section] = items
    return result


def abstract_and_keywords(pages: list[str]) -> tuple[dict[str, Any], list[str]]:
    abstract = {"text": "", "page_start": None, "page_end": None, "method": "not_found", "confidence": 0.0}
    keywords: list[str] = []
    for page_no, text in enumerate(pages[:6], 1):
        match = re.search(r"摘\s*要\s*[:：]?\s*", text)
        if match:
            tail = text[match.end():]
            stop = re.search(r"关\s*键\s*[词字]\s*[:：]?|\n\s*Abstract\b", tail, re.I)
            body = clean(tail[:stop.start() if stop else 1800])[:1800]
            if chars(body) >= 30:
                abstract = {"text": body, "page_start": page_no, "page_end": page_no, "method": "heading", "confidence": 0.9}
        key = re.search(r"关\s*键\s*[词字]\s*[:：]\s*([^\n]{2,240})", text)
        if key:
            keywords = [x.strip(" ;；,，。") for x in re.split(r"[；;,，、]", key.group(1)) if x.strip(" ;；,，。")]
        if abstract["text"] and keywords:
            break
    return abstract, keywords[:12]


def packet_paths(output: Path, record: dict[str, Any]) -> tuple[Path, Path]:
    stem = f"{record['id']}_{record.get('paper_code') or 'paper'}"
    base = output / str(record["year"]) / stem
    return base.with_suffix(".evidence.json"), base.with_suffix(".evidence.md")


def fingerprint(record: dict[str, Any], mode: str, dpi: int) -> str:
    value = f"{SCHEMA}|{VERSION}|{record.get('sha256')}|{mode}|{dpi}"
    return hashlib.sha256(value.encode()).hexdigest()


def build_packet(record: dict[str, Any], source: Path, pages: list[str], mode: str,
                 warnings: list[str], ocr_samples: list[dict[str, Any]], fp: str) -> dict[str, Any]:
    abstract, keywords = abstract_and_keywords(pages)
    nonempty = sum(bool(chars(x)) for x in pages)
    total = sum(chars(x) for x in pages)
    return {
        "schema_version": SCHEMA, "extractor_version": VERSION, "fingerprint": fp, "status": "success",
        "generated_at": now_iso(),
        "record": {k: record.get(k) for k in ("year", "id", "paper_code", "title", "source_page", "source_json", "asset_kind", "output_file", "sha256", "aliases")},
        "source_path": str(source), "page_count": len(pages), "extract_mode": mode,
        "text_stats": {"extractable_pages": nonempty, "total_chars": total, "chars_per_page": round(total / max(1, len(pages)), 2)},
        "abstract": abstract, "keywords": keywords,
        "problem_terms": term_hits(pages, PROBLEM_TERMS), "model_terms": term_hits(pages, MODEL_TERMS),
        "algorithm_terms": term_hits(pages, ALGORITHM_TERMS), "validation_terms": term_hits(pages, VALIDATION_TERMS),
        "section_excerpts": section_excerpts(pages),
        "ocr": {"engine": "RapidOCR", "version": importlib.metadata.version("rapidocr") if ocr_samples else None,
                "sampled_pages": ocr_samples, "coverage_note": "Only sampled pages were OCRed." if ocr_samples else "Not used."},
        "warnings": warnings,
    }


def markdown(packet: dict[str, Any]) -> str:
    r = packet["record"]
    lines = [f"# {r.get('paper_code') or r['id']} - {r['title']}", "", f"- 年份：{r['year']}", f"- 记录 ID：{r['id']}",
             f"- 提取方式：{packet['extract_mode']}", f"- 页数：{packet['page_count']}", f"- 证据字符：{packet['text_stats']['total_chars']}", ""]
    if packet["abstract"]["text"]:
        lines += ["## 摘要证据", "", f"第 {packet['abstract']['page_start']} 页：{packet['abstract']['text']}", ""]
    if packet["keywords"]:
        lines += ["## 关键词", "", "、".join(packet["keywords"]), ""]
    for label, key in (("模型词", "model_terms"), ("算法词", "algorithm_terms"), ("验证词", "validation_terms")):
        if packet[key]:
            lines += [f"## {label}", "", "、".join(f"{x['term']}（{x['count']}，页{x['pages']}）" for x in packet[key]), ""]
    lines += ["## 分节证据", ""]
    for section, items in packet["section_excerpts"].items():
        if items:
            lines += [f"### {section}", ""]
            for item in items:
                lines += [f"- 第 {item['page']} 页（{', '.join(item['matched_terms'])}）：{item['text']}", ""]
    if packet["warnings"]:
        lines += ["## 警告", ""] + [f"- {x}" for x in packet["warnings"]] + [""]
    return "\n".join(lines)


def rebuild_index(output: Path, run: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for path in sorted(output.glob("[0-9][0-9][0-9][0-9]/*.evidence.json")):
        try:
            p = json.loads(path.read_text(encoding="utf-8"))
            r = p["record"]
            entries.append({"year": r["year"], "id": r["id"], "paper_code": r.get("paper_code"), "title": r["title"],
                            "extract_mode": p["extract_mode"], "page_count": p["page_count"], "total_chars": p["text_stats"]["total_chars"],
                            "ocr_pages": [x["page"] for x in p["ocr"]["sampled_pages"]], "packet_json": str(path), "packet_md": str(path.with_suffix(".md"))})
        except Exception:
            continue
    index = {"schema_version": SCHEMA, "updated_at": now_iso(), "run": run, "count": len(entries),
             "by_mode": dict(Counter(x["extract_mode"] for x in entries)), "papers": entries}
    atomic_json(output / "index.json", index)
    return index


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("text", "ocr", "all"), default="all")
    ap.add_argument("--input-root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--year", action="append", default=[], help="repeat or comma-separate years")
    ap.add_argument("--record", action="append", default=[], help="repeat or comma-separate record IDs/paper codes")
    ap.add_argument("--ocr-dpi", type=int, default=105)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="representative-test limit after filtering")
    args = ap.parse_args()
    records = [r for r in load_inventory(args.inventory) if selected(r, parse_values(args.year), parse_values(args.record))]
    if args.limit:
        records = records[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    rendered = args.output / "rendered"
    pdftoppm = None
    engine = None
    counts = Counter()
    started = time.perf_counter()
    for number, record in enumerate(records, 1):
        source = args.input_root / Path(record["output_file"])
        json_path, md_path = packet_paths(args.output, record)
        try:
            text_pages, warnings = extract_pages(source)
            total = sum(chars(x) for x in text_pages)
            wanted_mode = "text" if total >= 500 else "ocr_sampled"
            if args.mode == "text" and wanted_mode != "text":
                counts["not_text"] += 1
                continue
            if args.mode == "ocr" and wanted_mode != "ocr_sampled":
                counts["not_ocr"] += 1
                continue
            fp = fingerprint(record, wanted_mode, args.ocr_dpi)
            if json_path.exists() and not args.force:
                old = json.loads(json_path.read_text(encoding="utf-8"))
                if old.get("fingerprint") == fp and old.get("status") == "success":
                    if not md_path.exists():
                        atomic_text(md_path, markdown(old))
                    counts["resumed"] += 1
                    print(f"[{number}/{len(records)}] RESUME {record['year']} {record['id']}", flush=True)
                    continue
            samples = []
            analysis_pages = list(text_pages)
            if wanted_mode == "ocr_sampled":
                if pdftoppm is None:
                    pdftoppm = locate_pdftoppm()
                    from rapidocr import RapidOCR
                    engine = RapidOCR()
                for page, reasons in sample_pages(len(text_pages)).items():
                    sample = ocr_page(source, str(record["id"]), page, reasons, rendered, engine, pdftoppm, args.ocr_dpi, fp)
                    samples.append(sample)
                    analysis_pages[page - 1] = sample["text"]
            packet = build_packet(record, source, analysis_pages, wanted_mode, warnings, samples, fp)
            atomic_json(json_path, packet)
            atomic_text(md_path, markdown(packet))
            counts[wanted_mode] += 1
            print(f"[{number}/{len(records)}] OK {record['year']} {record['id']} mode={wanted_mode} chars={packet['text_stats']['total_chars']}", flush=True)
        except Exception as exc:
            counts["failed"] += 1
            print(f"[{number}/{len(records)}] ERROR {record.get('id')}: {exc}", file=sys.stderr, flush=True)
    run = {"mode": args.mode, "filters": {"years": sorted(parse_values(args.year)), "records": sorted(parse_values(args.record))},
           "selected": len(records), "counts": dict(counts), "seconds": round(time.perf_counter() - started, 2)}
    index = rebuild_index(args.output, run)
    print(json.dumps({"run": run, "index_count": index["count"], "by_mode": index["by_mode"]}, ensure_ascii=False), flush=True)
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
