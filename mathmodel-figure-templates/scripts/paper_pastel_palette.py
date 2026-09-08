from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

MPL_DIR = Path.cwd() / ".mplconfig"
MPL_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_DIR))

import matplotlib as mpl
from cycler import cycler
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.font_manager import FontProperties, fontManager


CORE_COLORS = {
    "lavender": "#D9D3E8",
    "mint": "#DAEDD8",
    "cream": "#F0E8D8",
    "apricot": "#F2C17E",
    "coral": "#E79C96",
}

DERIVED_COLORS = {
    "lavender_outline": "#958BAE",
    "mint_outline": "#8FB59A",
    "coral_outline": "#CF7D77",
    "ink": "#2D2D2B",
    "muted": "#6F6B67",
    "axis": "#B9B4AC",
    "grid": "#E5E1DA",
    "paper": "#FFFFFF",
}

CATEGORY_COLORS = tuple(CORE_COLORS.values())


def _font_candidates() -> list[Path]:
    return [
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    ]


def register_cjk_font(font_path: str | Path | None = None) -> str:
    candidates = [Path(font_path)] if font_path else _font_candidates()
    for candidate in candidates:
        if candidate.exists():
            fontManager.addfont(str(candidate))
            return FontProperties(fname=str(candidate)).get_name()
    return "DejaVu Sans"


def apply_paper_style(font_path: str | Path | None = None) -> str:
    font_name = register_cjk_font(font_path)
    mpl.rcParams.update(
        {
            "font.family": font_name,
            "axes.unicode_minus": False,
            "figure.facecolor": DERIVED_COLORS["paper"],
            "axes.facecolor": DERIVED_COLORS["paper"],
            "savefig.facecolor": DERIVED_COLORS["paper"],
            "savefig.transparent": False,
            "axes.edgecolor": DERIVED_COLORS["axis"],
            "axes.labelcolor": DERIVED_COLORS["ink"],
            "text.color": DERIVED_COLORS["ink"],
            "xtick.color": DERIVED_COLORS["muted"],
            "ytick.color": DERIVED_COLORS["muted"],
            "grid.color": DERIVED_COLORS["grid"],
            "grid.alpha": 0.60,
            "axes.prop_cycle": cycler(color=CATEGORY_COLORS),
            "legend.frameon": False,
            "savefig.bbox": "tight",
        }
    )
    return font_name


def paper_sequential_cmap(name: str = "paper_pastel") -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list(
        name,
        [
            CORE_COLORS["lavender"],
            CORE_COLORS["cream"],
            CORE_COLORS["mint"],
            CORE_COLORS["apricot"],
            CORE_COLORS["coral"],
        ],
    )


def paper_diverging_cmap(name: str = "paper_pastel_diverging") -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list(
        name,
        [DERIVED_COLORS["lavender_outline"], "#F8F6F1", CORE_COLORS["apricot"], DERIVED_COLORS["coral_outline"]],
    )


def style_axes(ax, grid_axis: str = "y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, axis=grid_axis)
    ax.set_axisbelow(True)
    return ax


def color_cycle(count: int, colors: Sequence[str] = CATEGORY_COLORS) -> list[str]:
    if count < 0:
        raise ValueError("count must be non-negative")
    return [colors[index % len(colors)] for index in range(count)]


def save_figure(
    fig,
    output_stem: str | Path,
    formats: Iterable[str] = ("png", "pdf", "svg"),
    dpi: int = 300,
) -> list[Path]:
    stem = Path(output_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fmt in formats:
        fmt = fmt.lower().lstrip(".")
        path = stem.with_suffix(f".{fmt}")
        fig.savefig(path, dpi=dpi, facecolor=DERIVED_COLORS["paper"], transparent=False)
        written.append(path)
    return written
