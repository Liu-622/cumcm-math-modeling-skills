from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import numpy as np

from paper_pastel_palette import (
    CATEGORY_COLORS,
    CORE_COLORS,
    DERIVED_COLORS,
    apply_paper_style,
    paper_diverging_cmap,
    save_figure,
    style_axes,
)

apply_paper_style()

import matplotlib.pyplot as plt


def make_demo(seed: int = 20260907):
    rng = np.random.default_rng(seed)
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.4), constrained_layout=True)

    x = np.arange(7)
    ax = axes[0, 0]
    for index, color in enumerate(CATEGORY_COLORS):
        y = 8 + index * 5 + np.cumsum(rng.normal(2.0, 0.7, len(x)))
        ax.plot(x, y, marker="o", ms=3.5, lw=1.8, color=color)
        ax.fill_between(x, y - 2.2, y + 2.2, color=color, alpha=0.18)
    ax.set_title("折线图（含置信区间）")
    style_axes(ax)

    ax = axes[0, 1]
    groups = np.arange(4)
    width = 0.14
    for index, color in enumerate(CATEGORY_COLORS):
        values = 25 + groups * 14 + index * 4 + rng.normal(0, 2, len(groups))
        ax.bar(groups + (index - 2) * width, values, width, color=color, edgecolor="white")
    ax.set_xticks(groups, ["对照", "低剂量", "中剂量", "高剂量"])
    ax.set_title("分组柱状图")
    style_axes(ax)

    ax = axes[0, 2]
    for index, color in enumerate(CATEGORY_COLORS):
        px = rng.normal(2 + index * 1.5, 0.7, 12)
        py = 10 + px * 6 + rng.normal(index * 3, 6, 12)
        size = rng.uniform(30, 130, 12)
        ax.scatter(px, py, s=size, color=color, alpha=0.72, edgecolor="white", linewidth=0.5)
    ax.set_title("气泡散点图")
    style_axes(ax, "both")

    ax = axes[1, 0]
    corr = np.corrcoef(rng.normal(size=(200, 5)), rowvar=False)
    corr[0, 1] = corr[1, 0] = 0.72
    corr[2, 4] = corr[4, 2] = -0.48
    im = ax.imshow(corr, cmap=paper_diverging_cmap(), vmin=-1, vmax=1)
    for row in range(5):
        for col in range(5):
            ax.text(col, row, f"{corr[row, col]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("相关性热图")
    fig.colorbar(im, ax=ax, shrink=0.75)

    ax = axes[1, 1]
    data = [rng.normal(42 + index * 9, 8 + index, 80) for index in range(5)]
    parts = ax.violinplot(data, showmeans=False, showmedians=True, showextrema=False)
    for body, color in zip(parts["bodies"], CATEGORY_COLORS):
        body.set_facecolor(color)
        body.set_edgecolor(DERIVED_COLORS["ink"])
        body.set_alpha(0.70)
    parts["cmedians"].set_color(DERIVED_COLORS["ink"])
    ax.set_xticks(range(1, 6), ["组 A", "组 B", "组 C", "组 D", "组 E"])
    ax.set_title("小提琴图")
    style_axes(ax)

    ax = axes[1, 2]
    xx = np.linspace(0, 12, 60)
    layers = np.vstack(
        [
            13 + 2 * np.sin(xx / 2.0),
            18 + 3 * np.sin(xx / 2.7 + 0.7),
            15 + 2 * np.cos(xx / 2.4),
            12 + 2 * np.sin(xx / 3.1 + 1.5),
            10 + 1.5 * np.cos(xx / 2.9 + 0.4),
        ]
    )
    ax.stackplot(xx, layers, colors=CATEGORY_COLORS, alpha=0.92)
    ax.set_ylim(0, 85)
    ax.set_title("堆叠面积图")
    style_axes(ax)

    fig.suptitle("纯白论文科研五色配色演示", fontsize=17, weight="bold")
    return fig


def main():
    parser = argparse.ArgumentParser(description="Render the paper-pastel palette demonstration.")
    parser.add_argument("--output-dir", default="paper-palette-demo")
    parser.add_argument("--formats", nargs="+", default=["png", "svg"])
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    fig = make_demo()
    for path in save_figure(fig, output_dir / "paper_pastel_palette_demo", formats=args.formats):
        print(path)
    plt.close(fig)


if __name__ == "__main__":
    main()
