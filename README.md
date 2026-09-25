# CUMCM C 题全流程建模 Skills

[![Validate skills](https://github.com/Liu-622/cumcm-math-modeling-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/Liu-622/cumcm-math-modeling-skills/actions/workflows/validate.yml)

> 面向全国大学生数学建模竞赛（CUMCM）本科组 C 题的证据链驱动工作流：从题面与数据审计，到建模、代码、验证、图表、论文和隔离复现。

## 中文说明

### 这套 Skills 解决什么问题

数学建模最难的往往不是“知道一个模型名字”，而是把整条链路做完整：

**题面要求 → 数据与假设 → 模型规格 → 公式与代码 → 求解证据 → 独立验证 → 图表与论文 → 可复现提交**

本仓库以 `cumcm-c-national-prize-workflow` 为总控 Skill，并组合 11 个专项 Skill、共享规范、确定性审计脚本与论文资源。它把每个阶段的输入、输出、证据和回退条件显式化，适合完整解题、阶段验收、终稿审查和高强度赛前训练。

“国一标准”表示质量目标，不代表或承诺获奖。最终结论仍必须以当届题面、官方规则、真实数据和人工复核为准。

### C 题主工作流

| 阶段 | 核心任务 | 主要产物 |
| --- | --- | --- |
| P0 | 核对题面、附件、模板与规则 | 项目状态、原始文件哈希 |
| P1 | 题意拆解与数据契约 | 要求清单、字段与数据来源说明 |
| P2 | 透明基线与历史案例差异 | 基线结果、案例适用边界 |
| P3 | 模型规格与选择依据 | 变量、目标、约束、消融方案 |
| P4 | 数学—代码契约 | 符号表、公式映射、行为测试 |
| P5 | 求解与证书 | 结果、约束检查、求解器证据 |
| P6 | 冻结验证 | 留出测试、敏感性与稳健性分析 |
| P6R | 独立红队证伪 | 问题清单、严重性与关闭记录 |
| P7 | 图表与论文 | 图—主张—数据链、完整正文 |
| P8 | 隔离重建与总审计 | 可复现构建、终稿评分与放行结论 |

主工作流包含项目初始化、阶段门禁、证据哈希、陈旧证据检测、图件注册、独立红队记录、隔离重建和最终审计。当前自测覆盖 16 个关键场景。

### Skill 组成

```text
cumcm-c-national-prize-workflow/  C 题总控、阶段门禁与审计
├─ references/                    证据契约、模型验证、论文与红队规范
├─ scripts/                       初始化、门禁、审计、隔离构建与自测
├─ assets/                        论文图表配色与样式
└─ agents/openai.yaml             Skill 界面元数据

1start-mathmodel/                 建模项目启动与计划
2analysis-modeling/               题意分析、变量、模型与约束
3coding-visual/                   编程求解、数值验证与数据图表
4drawio/                          技术路线图和模型结构图
5writing/                         Typst / LaTeX 论文撰写
6verity/                          终稿一致性、编译与提交验收
cumcm-c-problem/                  C 题专项问题求解
math-modeling-skill/              建模方法与历史案例检索
mathmodel-figure-templates/       论文级科学绘图模板
typst-author/                     Typst 写作与排错
doctor/                           环境检查与安装向导
_references/                      跨 Skill 共享规范
```

### 安装到 Codex

官方的 Skill 结构以每个目录内的 `SKILL.md` 为入口，并可配套 `references/`、`scripts/` 和 `assets/`。本仓库是多个相互协作的 Skill，安装时要保留这些目录之间的同级关系。参见 [OpenAI Skills 文档](https://developers.openai.com/plugins/build/skills)。

1. 克隆仓库：

   ```powershell
   git clone https://github.com/Liu-622/cumcm-math-modeling-skills.git
   cd cumcm-math-modeling-skills
   ```

2. 将需要的 Skill 目录和 `_references` 复制到个人 Codex Skills 目录。默认位置通常是 `C:\Users\你的用户名\.codex\skills`；如果设置了 `CODEX_HOME`，则使用其中的 `skills` 子目录。

3. 至少同时安装下列目录，确保 C 题总工作流依赖完整：

   ```text
   _references
   1start-mathmodel
   2analysis-modeling
   3coding-visual
   4drawio
   5writing
   6verity
   cumcm-c-national-prize-workflow
   cumcm-c-problem
   math-modeling-skill
   mathmodel-figure-templates
   typst-author
   doctor
   ```

4. 新建一个 Codex 任务，明确调用：

   ```text
   使用 $cumcm-c-national-prize-workflow，读取当前 C 题题面和附件，先完成 P0 规则核对与项目初始化；每个阶段通过门禁后再继续。
   ```

不要只复制 `SKILL.md`。脚本、参考文档、样式文件和共享规范都是工作流的一部分。

### 本地验证

仓库提供无第三方 Python 依赖的发布前检查：

```powershell
python scripts/validate_repository.py
```

检查内容包括：

- 顶层 Skill 的 UTF-8 frontmatter、名称和描述；
- C 题主工作流所需的同级依赖；
- 不应提交的 `__pycache__` 与 `.pyc`；
- C 题主工作流的 16 项自测。

GitHub Actions 会在每次 push 和 pull request 时运行同一检查。

### 设计原则与边界

- 当前题面、附件和官方规则始终优先于历史经验。
- 基线模型必须先建立；复杂模型只有在公平消融中确有增益时才保留。
- 合成情景不能伪装成真实观测，测试集不能反向参与选型。
- 脚本门禁能检查结构、路径、哈希和可执行性，但不能单独证明数学正确、原创性或获奖结果。
- “85 分”只表示工作流内部的候选竞争力门槛，不是竞赛结果预测。
- 项目中包含第三方模板、资料与文档时，各自权利和署名要求仍由原作者或来源决定。

### 许可状态

本仓库当前没有声明覆盖全部内容的统一开源许可证。除非某个文件或子目录另有许可说明，否则不要推定其可以被任意复制、修改或再分发。正式公开推广前，建议逐项确认原创代码、第三方模板、参考资料和数据的授权边界，再由仓库所有者选择合适的许可证。

---

## English

### Overview

This repository provides an evidence-driven, end-to-end workflow for undergraduate C problems in the China Undergraduate Mathematical Contest in Modeling (CUMCM).

The primary `cumcm-c-national-prize-workflow` skill coordinates problem intake, data contracts, baseline modeling, mathematical and code specifications, solver evidence, frozen validation, independent red-team review, paper-ready figures, writing, isolated rebuilds, and final audit. Supporting skills cover analysis, implementation, visualization, Typst/LaTeX writing, and submission checks.

The phrase “national first-prize standard” describes an internal quality target. It is not an award guarantee.

### Install

Clone the repository and copy the skill folders plus `_references` into your Codex Skills directory while preserving their sibling layout. Do not copy only `SKILL.md`; the workflows depend on their scripts, references, assets, and shared specifications.

OpenAI’s documented skill structure uses a `SKILL.md` entry point with optional `references/`, `scripts/`, and `assets/`: [Build skills](https://developers.openai.com/plugins/build/skills).

### Validate

```powershell
python scripts/validate_repository.py
```

The validator checks all top-level skill manifests, required C-workflow dependencies, generated-file hygiene, and the primary workflow’s 16 self-tests. The same command runs in GitHub Actions on every push and pull request.

### License status

No single repository-wide open-source license has been declared. Do not assume permission to reuse or redistribute files unless a file or subdirectory provides its own license. Review third-party templates, references, and datasets before public redistribution.
