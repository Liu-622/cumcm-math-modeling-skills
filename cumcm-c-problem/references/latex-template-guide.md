# CUMCM 2026 LaTeX 排版规范

## 1. 模板地位

先完整读取 `../../_references/cumcm_2026_format_spec.md`。格式 PDF 是硬规范；[jayxin/cumcm](https://github.com/jayxin/cumcm) 的 2026 `cumcmthesis` 工程和本地 `5writing/templates/zh/cumcm-latex/` 是实现参考。`assets/template/example-source.tex` 属于历史示例，不得作为 2026 格式来源。

不要另起一套页面设计。优先由已核验的模板控制标题层级、字体、字号、页眉页脚和正文排版；必须保证 A4、四边页边距至少 2.5 cm、摘要页页码从1开始且页脚居中、无目录。

## 2. 电子版

使用模板提供的电子版方式，例如：

```latex
\documentclass[withoutpreface]{cumcmthesis}
```

需要黑白打印时再考虑 `bwprint`，但论文中图表应首先按屏幕评阅设计低饱和颜色，同时保证转灰度后仍能区分线型/标记。

电子版是一个不再压缩的 PDF/Word 文件，建议 PDF且不超过20MB。只有用户明确要求纸质版时，才另行生成包含当届承诺书和编号专用页的版本；两版除删除这两页外，正文和附录必须一致。

## 3. 第一页

第一页必须是：
- 论文标题；
- 摘要；
- 关键词。

摘要结束后显式 `\newpage`，确保“问题重述”从第2页开始。若摘要溢出，先删冗余，不通过缩小字号破坏模板。

第一页页脚中部必须显示阿拉伯数字 `1`，后续连续编号。2026 格式 PDF没有规定关键词数量；3–5个可作写作建议，但不能设为格式硬门。

## 4. 固定章节骨架

优先：

```latex
\section{问题重述}
\section{问题分析}
\section{模型假设}
\section{符号说明}
\section{模型的建立与求解}
  \subsection{问题一的模型建立与求解}
  ...
\section{模型评价与推广}
\begin{thebibliography}{99}
...
\end{thebibliography}
\begin{appendices}
...
\end{appendices}
```

若优秀范文和当前题目更适合把每问设为一级章节，可以微调，但全文层级必须一致。

## 5. 公式

普通推导使用 `equation/align`。完整优化模型在解释完每个组件后集中展示：

```latex
\begin{equation}
\boxed{
\left\{
\begin{aligned}
\max_{x_{ijt}}\quad & Z=\sum_{i,j,t} r_{ijt}x_{ijt},\\
\text{s.t.}\quad
& \sum_i x_{ijt}\le A_j,\\
& x_{ijt}\ge 0,\\
& x_{ijt}\in\mathbb{Z}\quad \text{(when needed)}.
\end{aligned}
\right.
}
\label{eq:main-model}
\end{equation}
```

不要用大段文字取代约束，也不要堆几十行方程组看不清。可把约束分组并在式后逐条解释。

## 6. 表格

严格使用 `booktabs` 三线表；避免竖线。表头简洁，单位优先写到列名。小数位按实际精度统一。

## 7. 图片

图片文件使用英文/数字有意义命名：
- `overview_model.pdf`
- `sales_week_pattern.png`
- `strategy_phase_map.pdf`

不要使用 `1.png`, `图3.png`。

矢量图优先 PDF；位图 200–300 dpi。Overview 图、网络图优先 TikZ 或矢量工具，避免截图。

## 8. 页数、附录和支撑材料

本包用户指定正文25–28页为验收硬门，含参考文献，摘要专用页和附录不计入；范围外不通过。该要求不冒充官方格式条款，也不得通过 `\vspace` 拉页或缩小边距压页。

附录从新页开始，必须列出支撑材料中的全部文件名，并嵌入建模使用的全部完整、可运行源程序及 Excel/SPSS 等交互命令；完整代码还要同时放入支撑材料。只放核心片段不合格。无程序或无支撑材料时分别使用“本论文没有用到程序”“本论文没有支撑材料”。

支撑材料打成一个不超过20MB的ZIP/RAR，包含完整代码、自主查阅数据和必要的大篇幅中间结果；不重复打包赛题原始数据。文件清单必须与压缩包逐项一致。

## 9. 匿名、引用与 AI 声明

- 最终 PDF、TeX、图表、代码、文件名、PDF元数据和支撑包不得出现参赛者、学校或赛区身份信息。
- 所有公开资料在正文引用处标注，并列入参考文献。
- 若使用 AI，按当届 AI 工具规定及真实使用情况生成声明和支撑材料详情；AI要求须回到当届规则核验，不能声称来自论文格式 PDF。
