---
name: cumcm-c-national-prize-workflow
description: 面向 CUMCM 本科组 C 题的分阶段建模、验证、论文与复现工作流。用于完整解题、逐步验收、终稿审查或国一标准训练，不用于其他题型。
---

# CUMCM C 题工作流

## 目标与边界

以全国一等奖竞争力为质量目标，当前题面、附件和当届规则优先于历史经验。`quality_status` 由证据决定，`user_review` 只记录人工验收；人工确认可豁免，但不能把非 PASS 自动改成 PASS。

脚本门禁检查结构一致性、路径、可执行测试、隔离构建和证据哈希。它们不是防篡改安全边界，也不能单独证明数学真理、原创性或获奖结果；涉及语义和科学正确性的门仍须由独立审查证据支持。

## 启动与恢复

- 无 `workflow_state.json`：核对题面、附件、模板和规则后，运行本 skill 的 `cumcm-c-national-prize-workflow/scripts/init_project.py`；原始文件复制到 `data/raw/` 并登记 SHA-256。不要误用 `cumcm-c-problem/scripts/init_project.py`，后者只生成独立的 C 题 LaTeX 骨架。
- 已存在：运行本 skill 的 `cumcm-c-national-prize-workflow/scripts/gate.py <project> status`，从当前阶段继续。
- 可在 `config/team_profile.json` 填写编程语言、硬件、时间和优先目标；这是选型约束，不是质量门。
- v1 状态或升级后的v2项目：运行 `scripts/gate.py <project> migrate` 补齐新资源；不能验证的新字段保持 `UNVERIFIED`。
- 不覆盖原始附件；派生数据、结果和图件写入新路径。
- 本文件的脚本路径相对本 skill 目录，不相对建模项目；先解析实际安装路径，再用已验证的 Python 解释器运行脚本，项目路径作为带引号参数传入。Windows/PowerShell 不依赖直接执行 `.py`、Bash 或 Linux 专属目录。共享参考位于本 skill 同级的 `_references/`，缺失时报告依赖缺口，不假称已读取。

阶段顺序和回退条件见 [阶段门与回退](references/stage-gates.md)：

`P0 规则 → P1 题意/数据契约 → P2 基线/历史差异 → P3 模型规格 → P4 数学/代码契约 → P5 求解/证书 → P6 冻结验证 → P6R 独立证伪 → P7 图表/论文 → P8 隔离重建/评分`

每阶段用 `scripts/gate.py` 提交报告和项目内证据路径。P1区分题面明确要求与有依据的推断要求，并区分题目数据、外部数据和仅用于压力测试的合成情景；P1、P2由 `scripts/phase_contract_audit.py` 执行结构门。P3后按 [证据契约](references/evidence-contracts.md) 维护注册表，所有路径相对项目根。

## 建模与验证

P2—P6按 [模型选型与验证](references/model-selection-and-validation.md) 执行。每问先建立透明基线；增强结构只有在当前数据中激活且公平消融优于基线时才保留。真实观测的留出集预先隔离，模型和主张冻结后才开启终检；可生成的新测试情景在冻结后生成。最终测试不参与选型；策略比较优先采用共同随机环境的配对设计。

P4的关键假设必须记录依据、模型影响、失效条件和敏感性接口；全局符号记录类型、单位、定义域、作用域和代码名。P5保留数据处理决策日志及处理前后样本量，合成数据只能标为情景数据，不能伪装成观测。公式—代码契约必须包含行为测试。

P6按预测、分类、评价、优化、机理或仿真类型选择验证指标，说明选择依据、实验设计和通过阈值。限时或启发式优化报告 incumbent、best bound、gap 和停止原因；核心问题 gap 超过20%且无补强证据时不能作为国一终稿通过。约束不适用记 `N_A`，不得填0。

按阶段读取并使用专业 Skill：P0 用 `1start-mathmodel`；P1/P3/P4 用 `2analysis-modeling`；P2 结合 `math-modeling-skill` 与 `cumcm-c-problem`；P5 用 `3coding-visual`；P7 用 `3coding-visual`、`4drawio`、`mathmodel-figure-templates`、`5writing`；P8 用 `6verity`。调用前完整读取对应 `SKILL.md`。数据/统计图表优先用 `mathmodel-figure-templates`（命中模板 id 时），未命中模板的自绘图才用 `3coding-visual`。

## 独立红队

P6R按 [独立红队协议](references/red-team-protocol.md) 执行。审查者必须来自不同子任务上下文或外部审查者，且不得接收原自评分或预期结论。完成后用 `scripts/record_red_team.py` 写入审查者类型、不同的生产/审查上下文 ID、输入哈希、报告哈希和问题状态；不能取得不同审查上下文时保持 `UNVERIFIED`。

该记录提供可追溯性与陈旧检测，不是密码学身份认证。

## 图表与论文

按 [可视化证据链](references/visualization-strategy.md) 建立图—主张—数据—脚本关系。初始化时视觉资产复制到 `support/visual-style/`；数据/统计图优先调用 `mathmodel-figure-templates`，命中模板 id 时套用其脚本与纯白论文配色（`style_policy=TEMPLATE`）；未命中模板的 Matplotlib 图必须实际加载 `cumcm.mplstyle` 和 `palette.json`（`style_policy=CUMCM_V1`），非 Matplotlib 图登记豁免理由（`EXEMPT`）。运行 `scripts/figure_registry.py audit <project>`。

P7、P8按 [论文质量门](references/paper-quality-gates.md) 执行，逐章成稿写法见 [论文写作规范](references/paper-writing-conventions.md)。CUMCM 2026项目还必须完整读取 `../_references/cumcm_2026_format_spec.md`，其PDF条款作为格式硬门。摘要最后写，只使用 `INCLUDE + PASS` 主张和冻结结果。`evidence/writing_audit.json` 必须给出有证据的优点、带适用边界的缺点，并检查术语、符号、章节承诺和关键数字一致性。

本包按用户明确要求执行正文25–28页硬门（含参考文献，不含摘要页和附录），超出区间不得P7/P8 PASS；不得凑页。各问不固定篇幅、模型数量或假设数量，也不得为“创新”堆叠模型、虚构观测数据、文献、结果或性能提升。

## 隔离重建与最终放行

在 `evidence/build_plan.json` 中用参数数组声明复制输入、构建步骤和预期产物；不得依赖原项目中的已有结果。运行：

```text
scripts/run_clean_build.py <project>
scripts/clean_build_audit.py <project>
```

脚本会创建新的 `build/clean/<run-id>/workspace`、删除其中同名预期产物、真实执行命令并记录退出码、日志、输入快照和产物哈希。编译器缺失、命令失败或产物未重新生成时只能失败。

提交 P8 时，`gate.py` 自动执行证据、图件、构建和评分检查；完成后只需运行一次总审计：

```text
scripts/audit_project.py <project> --output reports/FINAL_AUDIT.json
```

P8 PASS 要求：所有阶段质量状态 PASS、红队无未关闭严重问题、隔离构建有效、无未验证评分项，且封顶后总分不低于 85。85 分仅表示国一候选竞争力，不构成获奖保证。
