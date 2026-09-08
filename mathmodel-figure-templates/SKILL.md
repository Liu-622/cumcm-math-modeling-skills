---
name: mathmodel-figure-templates
description: Reproduce bundled scientific visualization templates or apply a pure-white, paper-ready scientific palette with Python and matplotlib. Use for 科研绘图模板, 论文配色, SHAP蜂群柱状图, 配对云雨图, 交叉验证ROC, 泰勒图, 相关矩阵组合图, 预测真实值边缘分布图, TPE调参3D曲面, 分组环形热图, and Nature和弦图 requests in local Windows, macOS, or Linux projects.
---

# MathModel Figure Templates

This skill contains Python/matplotlib figure templates. Resolve all bundled paths relative to the directory containing this `SKILL.md`; do not assume a particular user directory, app, or operating system. Use an available Python 3.10+ interpreter with `numpy` and `matplotlib` installed, and check those imports before rendering.

## Fast Path

1. Match the requested chart in `references/figure-catalog.md`.
2. From the user's project directory, run the renderer with the template id. Replace `<skill-directory>` with this skill's resolved directory; quote paths containing spaces. This command works in PowerShell and POSIX shells when `python` is available (otherwise substitute the verified interpreter):

```text
python -X utf8 "<skill-directory>/scripts/render_template.py" paired-raincloud
```

3. For a standalone demonstration, the renderer copies the bundled template script into `绘图复刻/scripts/`, runs it there, and writes outputs to `绘图复刻/outputs/`.
4. Return the generated PNG/PDF/SVG paths and the copied script path to the user.

Use `--list` to show supported ids:

```text
python -X utf8 "<skill-directory>/scripts/render_template.py" --list
```

## Output Contract

- Work under the current workspace unless the user gives another path.
- Default project folder: `绘图复刻`.
- Script path: `绘图复刻/scripts/make_<template>.py`.
- Outputs: `绘图复刻/outputs/<template>_replica.png`, `.pdf`, `.svg`.
- Use the bundled scripts as the first choice; edit the copied workspace script only when the user requests customization.
- The bundled scripts use deterministic simulated data. Do not claim simulated values reproduce a source study exactly.
- When producing a real modeling result, replace simulated values with validated task data and recompute all displayed statistics before including the figure in a paper. Label demonstration exports as simulated examples.

## Modeling Workflow Integration

For a project managed by `cumcm-c-national-prize-workflow`, use the project mode instead of manually moving files:

1. Prepare the editable script without registering simulated output:

```text
python -X utf8 "<skill-directory>/scripts/render_template.py" paired-raincloud --project "<modeling-project>" --workflow --prepare
```

2. Edit `<modeling-project>/code/figures/make_paired_raincloud.py` so it reads validated project data and documents fields, transformations, encodings, and uncertainty.
3. After the referenced claim is `PASS + INCLUDE` in `evidence/claims.json`, render and register the real-data figure:

```text
python -X utf8 "<skill-directory>/scripts/render_template.py" paired-raincloud --project "<modeling-project>" --workflow --confirm-real-data --figure-id fig_q2_03 --question Q2 --claim-id Q2-C01 --claim "<falsifiable claim>" --source-file "results/q2.csv" --paper-section "问题二结果"
```

Workflow mode keeps the adapted script in `code/figures/`, writes PNG/PDF/SVG to `figures/`, computes source hashes, and updates `evidence/figures.json` with the explicit `template_id`. The command refuses registration without the confirmation flag, required metadata, existing source files, and existing `PASS + INCLUDE` claims. Run the workflow's `figure_registry.py audit` afterward. `--confirm-real-data` is an assertion about the adapted script; inspect the script and outputs rather than adding the flag to an untouched simulated template.

## Template Ids

- `multiclass-shap-combo`
- `paired-raincloud`
- `cv-roc-ci`
- `taylor-diagram`
- `correlation-pairgrid`
- `prediction-marginal-grid`
- `rf-tpe-surface`
- `grouped-corr-split-violin`
- `grouped-circular-heatmap`
- `urban-park-cooling-combo`
- `nature-chord-diagram`

## When Customizing

If the user asks for changes, copy/run the nearest template first, then edit the copied file in `绘图复刻/scripts/`. Preserve:

- `MPLCONFIGDIR` before importing matplotlib.
- deterministic seeds for simulated data.
- PNG/PDF/SVG export.
- readable labels, legends, and high-DPI output.

Use `references/plot-recipes.md` for implementation patterns.

## Pure-White Paper Palette

When the user requests a restrained CUMCM paper style, a pure-white page background, or the preferred pastel comparison version:

1. Read `references/paper-pastel-palette.md`.
2. Copy `scripts/paper_pastel_palette.py` beside the workspace plotting script and import its helpers instead of redefining colors.
3. Keep the figure and axes backgrounds pure white. Use the five core colors for filled marks and the derived darker colors only for thin lines, outlines, and text that needs contrast.
4. For figures embedded in a paper, size them to the text block rather than a slide canvas. Add a short modeling motivation before the figure, a numbered caption below it, and a result interpretation after it.

Run `scripts/make_paper_palette_demo.py --output-dir <directory>` to render a deterministic PNG/SVG demonstration of the palette before adapting a larger report.
