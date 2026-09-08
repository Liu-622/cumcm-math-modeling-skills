# Pure-White Paper Palette

Use this palette when the user asks for a restrained, comfortable, paper-integrated style. The colors and rules below are self-contained; no external sample PDF is required. These are visual preferences, not universal competition rules.

## Core colors

| Role | Hex | Recommended use |
| --- | --- | --- |
| Lavender | `#D9D3E8` | Group A, confidence bands, low-intensity fills |
| Mint | `#DAEDD8` | Group B, comparison fills, positive/supporting categories |
| Cream | `#F0E8D8` | Neutral regions, background bands, middle values |
| Apricot | `#F2C17E` | Highlights, Group D, important but non-alarm states |
| Coral | `#E79C96` | Group E, upper values, warnings, primary emphasis |

Use the colors in this order for categorical charts unless the data semantics require another order.

## Derived support colors

The five core colors are intentionally light. Use these derived colors where thin marks need more contrast:

- Lavender outline: `#958BAE`
- Mint outline: `#8FB59A`
- Coral outline: `#CF7D77`
- Main text: `#2D2D2B`
- Secondary text: `#6F6B67`
- Axes: `#B9B4AC`
- Grid: `#E5E1DA`
- Figure and axes background: `#FFFFFF`

Do not replace the paper background with cream. Cream is a data color, not the page color.

## Chart rules

- Lines: use a derived outline color at `1.6-2.2 pt`; do not use cream for an unoutlined thin line.
- Confidence intervals and density fills: use a core color at `0.15-0.28` alpha.
- Bars, violins, and stacked areas: use core colors with a white separator or a darker outline.
- Scatter plots: use core colors at `0.55-0.78` alpha and add a darker edge only when points overlap heavily.
- Sequential maps: interpolate lavender -> cream -> apricot -> coral.
- Diverging correlation maps: use darker lavender for negative values, near-white for zero, and apricot/coral for positive values.
- Encode important distinctions with marker shape, line style, label, or annotation as well as color.

## Paper integration

- Follow the competition template or the user's page-size requirement (commonly A4); keep the chart itself pure white.
- Typical figure width: `0.78-0.92` of the text block; keep a single figure below roughly one third of page height when possible.
- Place a short modeling motivation before the figure, a numbered caption immediately below it, and a result interpretation after it.
- Keep captions, axes, and legends readable at the final embedded size. Check the rendered PDF rather than the source canvas alone.
- Export PNG at 300 dpi and also export PDF or SVG when the downstream paper tool supports vector figures.

## Python helper

Copy `scripts/paper_pastel_palette.py` beside the plotting script, then use:

```python
from paper_pastel_palette import (
    CORE_COLORS,
    apply_paper_style,
    paper_diverging_cmap,
    paper_sequential_cmap,
    save_figure,
    style_axes,
)

apply_paper_style()
```

The helper sets `MPLCONFIGDIR` before importing Matplotlib, uses a deterministic color cycle, and preserves a pure-white export background.
