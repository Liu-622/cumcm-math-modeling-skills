# CUMCM Math Modeling Skills 4.0

> 面向全国大学生数学建模竞赛（CUMCM）的可复用 AI 建模工作流与技能库。  
> 从读题、建模、编程、可视化，到论文排版、验证和提交验收，帮助你把“想法”推进成“可复现、可检查、可提交”的完整成果。

## 中文介绍

### 这是什么？

这是一个为数学建模竞赛和科研型建模任务整理的 Skills 集合，适用于 Codex 等支持技能调用的智能编程环境。它把竞赛中最容易遗漏的环节沉淀为清晰的阶段化流程：

**题面理解 → 数据审计 → 假设与变量 → 模型设计 → 算法求解 → 结果验证 → 图表制作 → 论文撰写 → 终稿验收**

每个阶段都有对应的入口、检查点和可复用模板，强调证据链、数值一致性、可复现性和论文质量，而不是只给出一个“看起来合理”的模型名称。

### 核心能力

- **完整工作流**：`1start-mathmodel` 负责启动项目并生成计划，串联分析、代码、图示、写作和验收阶段。
- **赛题分析与建模**：`2analysis-modeling` 和 `math-modeling-skill` 覆盖问题拆解、变量定义、目标函数、约束、预测/评价/优化/分类/聚类/网络/仿真等建模范式。
- **可复现求解与可视化**：`3coding-visual` 负责实现模型、运行求解、检查约束、输出结果报告，并生成论文可用图表。
- **技术路线图与流程图**：`4drawio` 将模型结构、数据处理和子问题求解过程整理为可引用的 DrawIO/PDF 图示。
- **中英文论文成稿**：`5writing` 提供 Typst 与 LaTeX 双引擎模板，覆盖中文/英文、MCM/APMCM 等常见论文结构。
- **终稿质量控制**：`6verity` 检查章节、图表引用、数值一致性、占位符、参考文献、代码复现和编译状态。
- **C 题专项支持**：`cumcm-c-national-prize-workflow` 与 `cumcm-c-problem` 面向本科组 C 题，强调数据分析、机制解释、稳健验证和国一标准的论文审查。
- **绘图与排版资源**：`mathmodel-figure-templates` 提供论文级配色和科学可视化模板；`typst-author` 辅助 Typst 文档编写与排错。
- **资料与规范**：`_references`、`国赛资料` 和各 skill 内的模板、示例与检查规则，便于在比赛中快速查阅。

### 目录一览

```text
1start-mathmodel/                 工作流入口
2analysis-modeling/               题面分析与模型设计
3coding-visual/                   编程求解、验证与图表
4drawio/                          技术路线图与流程图
5writing/                         Typst/LaTeX 论文生成
6verity/                          最终验收
cumcm-c-national-prize-workflow/  C 题国一标准工作流
cumcm-c-problem/                  C 题专项建模支持
math-modeling-skill/              通用建模方法库
mathmodel-figure-templates/       论文级可视化模板
typst-author/                     Typst 写作与排错
doctor/                           环境检查与安装向导
_references/                      格式规范与写作规范
国赛资料/                         竞赛参考资料
```

### 如何使用

1. 将本仓库放入你的 Codex Skills 目录，或在支持 Skills 的环境中打开本项目。
2. 先调用 `1start-mathmodel`，提供题面和附件，生成项目计划。
3. 按阶段调用 `2analysis-modeling`、`3coding-visual`、`4drawio`、`5writing` 和 `6verity`。
4. 每个阶段完成后阅读生成的报告和检查结果，再进入下一阶段；不要跳过数据审计、验证和终稿验收。

如需检查本机解释器、编译器、绘图库和 PDF 工具，可使用 `doctor`。论文模板位于 `5writing/templates/`，支持 Typst 和 LaTeX 两套方案。

### 设计理念

本项目不承诺“自动得到唯一最优答案”，而是帮助你建立一条可信的建模证据链：数据从哪里来、假设为何成立、模型如何求解、结果是否满足约束、图表是否与正文一致、代码能否被他人复现。最终产出应由使用者结合题面、数据和比赛要求审阅确认。

## English

### What is this?

**CUMCM Math Modeling Skills 4.0** is a reusable, evidence-oriented skill library for the China Undergraduate Mathematical Contest in Modeling (CUMCM) and research-style modeling projects.

It turns the entire modeling process into a traceable pipeline:

**Problem understanding → Data audit → Assumptions and variables → Model design → Algorithmic solution → Validation → Visualization → Paper writing → Final quality gate**

The collection is designed for Codex and other skill-enabled AI coding environments. It focuses on reproducibility, constraint checking, numerical consistency, and submission-ready writing—not on naming a model without completing the reasoning chain.

### Highlights

- **End-to-end orchestration** with `1start-mathmodel`.
- **Problem decomposition and model formulation** through `2analysis-modeling` and `math-modeling-skill`.
- **Reproducible code, solvers, validation, and paper-ready figures** in `3coding-visual`.
- **DrawIO/PDF technical route maps and solution flowcharts** via `4drawio`.
- **Chinese and English Typst/LaTeX paper templates** in `5writing`, including MCM/APMCM layouts.
- **Final submission quality gates** in `6verity`, covering structure, references, figures, numbers, placeholders, compilation, and reproducibility.
- **Dedicated undergraduate C-problem workflows** in `cumcm-c-national-prize-workflow` and `cumcm-c-problem`.
- **Scientific visualization templates, Typst references, competition materials, and writing standards** included in the repository.

### Quick start

1. Open this repository in Codex or another environment that supports Skills.
2. Start with `1start-mathmodel` and provide the problem statement and attachments.
3. Follow the generated plan through analysis, implementation, diagrams, writing, and verification.
4. Review every report and validation result before moving to the next stage.

Use `doctor` to inspect the local modeling environment. Paper templates are available under `5writing/templates/` in both Typst and LaTeX.

### Philosophy

The toolkit does not claim to produce a magically unique optimum. Its purpose is to make every important modeling decision inspectable and reproducible: data provenance, assumptions, formulation, solver behavior, constraint satisfaction, figure–text consistency, and runnable code. Always review the generated artifacts against the original problem and contest requirements.

## License and attribution

Please respect the licenses and attribution requirements of the bundled templates, references, and third-party materials. Add your own citation or license information when redistributing derived work.
