# 证据契约与评分封顶

## 注册表共同规则

所有注册表使用UTF-8 JSON，顶层含 `schema_version: "2.0"`。路径相对于项目根。一般验收状态为 `PASS | FAIL | UNVERIFIED`；约束不适用时按下文使用 `N_A`，图表规划状态按图表注册表规范填写。`PASS`记录引用的文件必须真实存在。

`evidence/figures.json` 中 `style_policy=TEMPLATE` 的记录必须含显式、短横线格式的 `template_id`（例如 `paired-raincloud`）以及非空 `style_evidence`。模板身份由注册字段核验，不通过搜索绘图脚本内的 `MPLCONFIGDIR` 或调色板名称推断。真实图仍需记录 `source_files`、哈希、`claim_ids`、脚本和输出路径；模拟模板不能登记为 `GENERATED` 或 `FINAL` 的论文证据。

## P1 问题与数据契约 `evidence/problem_contracts.json`

`questions`为每问记录任务动词、输入、输出、指标、约束、下游接口、验证、单位状态、时间方向和结果模板映射。`requirements`中的每项含 `type=EXPLICIT|INFERRED`、完整陈述、依据和状态；至少存在一项题面明确要求，推断项不能没有依据。

`data_fields`逐字段记录含义、单位、对象、时间基准、来源、`source_type=PROVIDED|EXTERNAL|SYNTHETIC_SCENARIO`、来源引用、是否为观测和缺失策略。合成情景必须 `observed=false`，只能用于情景或压力分析。P1 PASS前运行 `phase_contract_audit.py`。

## P2 基线 `evidence/baselines.json`

每问至少一个基线，记录方法、目标输出、失败条件、当前数据证据和 `historical_review`。历史案例按数学结构记录相似点、差异、可迁移内容和禁止迁移内容；没有可迁移案例时允许 `cases=[]`，但必须给出 `no_transfer_reason`。

## 论文主张 `evidence/claims.json`

每项至少包含：

```json
{
  "claim_id": "Q2-C01",
  "question": "Q2",
  "kind": "result|innovation|robustness|optimality|mechanism",
  "disposition": "INCLUDE",
  "wording": "论文拟使用的完整主张",
  "allowed_language": ["在给定情景内"],
  "forbidden_language": ["全局最优"],
  "formula_ids": ["Q2-E01"],
  "evidence_files": ["results/q2_test.csv"],
  "experiment_ids": ["EXP-Q2-TEST"],
  "activation_status": "PASS",
  "falsifier": "何种结果会推翻本主张",
  "status": "PASS"
}
```

`disposition`只能为 `INCLUDE` 或 `EXCLUDE`。进入论文的主张必须为INCLUDE且PASS；被证伪的候选可保留为EXCLUDE，且不再要求激活通过。只有INCLUDE创新必须通过激活；结果和稳健性主张必须引用实验；最优性主张必须引用优化证书。

## 模型契约 `evidence/model_contracts.json`

每项包含 `formula_id`、`code_path`、`test_path`、`tested_invariants`、`evidence_files`、`status`。`tested_invariants`不得为空，且至少包含一个行为性质，而不是“函数存在”。

同一文件的 `assumptions` 记录假设陈述、依据、模型影响、失效条件、是否关键、关联敏感性ID和状态；关键假设在P6前必须关联已通过的敏感性分析。`symbols`记录符号、含义、类型、单位、定义域、代码名、作用域和状态。数量由实际模型决定，不为满足格式凑数。

## 数据处理 `evidence/data_processing.json`

每项记录 `decision_id`、处理范围、发现的问题、`action=KEEP|IMPUTE|REMOVE|TRANSFORM|FLAG`、依据、处理前后样本量、数据角色、证据文件和状态。即使不处理，也用KEEP说明为何保留。合成数据只能标为 `SYNTHETIC_SCENARIO`，并记录 `used_as_observed=false` 与假设依据。

## 实验 `evidence/experiments.json`

每项包含：

```json
{
  "experiment_id": "EXP-Q3-PAIR",
  "role": "TRAIN|VALIDATION|FINAL_TEST|STRESS",
  "purpose": "Q2/Q3共同环境配对比较",
  "data_files": ["results/common_test.csv"],
  "seed": 20240901,
  "sample_size": 800,
  "model_frozen_before_run": true,
  "used_for_selection": false,
  "paired_environment_id": "ENV-FINAL-01",
  "compared_plans": ["Q2", "Q3"],
  "status": "PASS"
}
```

`FINAL_TEST`必须满足模型先冻结且未用于选型。声称策略比较的多个实验必须共享 `paired_environment_id`；若在同一实验文件内比较，登记至少两个 `compared_plans`。无法配对时不得把环境差异归因于策略。

同一文件的 `validation_protocols` 按每问记录问题类型、指标、选取依据、实验设计、通过阈值、证据文件和状态。问题类型允许预测、分类、评价、优化、机理、仿真或其他；不能把某类模型的常用指标机械套给所有问题。

## 优化证书 `evidence/optimization_certificates.json`

每项包含 `certificate_id`、`question`、`core`、`incumbent`、`best_bound`、`sense`、`absolute_gap`、`relative_gap`、`runtime_seconds`、`termination`、`solver`、`structure_scope`、`allowed_language`、`status`。

`relative_gap > 0.20` 且 `core=true` 时触发国一终稿封顶；若无法获得best bound，状态为 `UNVERIFIED`，不能以0代替。

## 敏感性 `evidence/sensitivity.json`

每项包含 `analysis_id`、`target`、`perturbation_type`、`decision_policy`、`mean_preserving`、`range`、`sample_size`、`seed`、`evidence_files`、`status`。

`perturbation_type=variance` 时必须 `mean_preserving=true`；`decision_policy`只能为 `FIXED_PLAN` 或 `REOPTIMIZED`。

## 约束证书 `evidence/constraint_certificates.json`

每项包含 `plan_id`、`constraint_id`、`applicability`、`status`、`max_violation`、`tolerance`、`evidence_file`。`applicability=false` 时状态必须为 `N_A`，且 `max_violation`为null；适用时不能使用 `N_A`。

## 红队 `evidence/red_team.json`

只能由 `record_red_team.py` 从审查报告生成。记录包含审查者类型、不同的生产/审查上下文ID、报告及输入哈希、严重问题、复现步骤、回退阶段和关闭证据。存在未关闭 `CRITICAL` 或 `MAJOR` 问题时不得PASS。该记录提供可追溯性和陈旧检测，不构成密码学身份认证。

## 干净重建 `evidence/build_verification.json`

先在 `evidence/build_plan.json` 以 `copy_paths`、`steps[].argv/cwd/timeout_seconds` 和 `artifacts` 声明构建。`run_clean_build.py` 在新隔离目录真实执行参数数组命令并生成 `build_verification.json`。手写PASS、只登记命令或复用既有产物不能通过审计。

## 写作审计 `evidence/writing_audit.json`

`strengths`中的每项必须有证据文件；`limitations`还需写明适用边界。`consistency_checks`至少覆盖 `TERMS`、`SYMBOLS`、`SECTION_PROMISES`、`NUMBERS`、`PAGE_BUDGET` 和 `PADDING`，并引用论文源、检查报告或结果文件。`PAGE_BUDGET`记录适用页数限制、来源、实际章节分配和用户明确目标（如有），未指定时不检测最低页数；`PADDING`记录经语义确认的冗余及位置，不自动删除必要定义。不得虚构文献、性能提升或数值，不按固定标题、模型数、假设数、参考文献数或页数填充内容；论证不足时补充真实且必要的分析，已充分时不扩写凑页。

## CUMCM格式审计 `reports/CUMCM_FORMAT_AUDIT.json`

CUMCM 2026项目用 `6verity/scripts/cumcm_format_check.py` 对最终电子版PDF、论文源和支撑材料生成审计。报告必须为PASS，且记录的PDF、源文件和支撑材料SHA-256必须与P8提交文件一致；重新编译、改正文或重打压缩包后必须重跑。程序检查不能替代逐页视觉检查、完整代码核对、真实身份排查或纸质装订检查。

## 评分 `evidence/scoring.json`

原始维度分总和为100，并记录理由。最终分先计算原始总分，再应用硬伤封顶：

| 硬伤 | 总分上限 |
|---|---:|
| 核心公式—代码契约失败 | 59 |
| CUMCM官方格式审计未通过 | 59 |
| 最终测试参与选型或严重比较不公平 | 69 |
| 核心问题gap大于20%且无补强证据 | 79 |
| 论文或关键结果无法从干净目录复现 | 79 |

未激活创新不一定封顶，但该创新在创新维度计0。评分报告必须同时给出原始分、封顶原因、最终分、未验证项和优先改进顺序。

每个维度必须给出证据化评分理由。国一工作流P8要求无未验证项且封顶后的最终分不低于85；85分只表示国一候选竞争力，不构成奖项保证。

## 自动审计边界

脚本检查结构、项目内路径、可执行结果和可判定不变量，不能证明模型科学正确，也不是防篡改安全边界。自动PASS不能替代P6R；自动FAIL必须修复。
