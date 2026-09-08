# 贡献指南

感谢参与数学建模竞赛专家 Skill。这个仓库采用“问题先讨论、修改走分支、结果经 PR、自动检查与人工审查后进入 `main`”的协作方式。

## 1. 开始之前

1. 确认你已获得本私有仓库的授权访问；
2. 阅读 [README.md](README.md)、[贡献授权约定](CONTRIBUTOR-AGREEMENT.md)和[第三方来源说明](THIRD-PARTY-NOTICE.md)；
3. 搜索现有 Issue 和 PR，避免重复工作；
4. 较大修改先开 Issue，说明目标、范围、证据和验收标准；
5. 不要把原始论文、扫描图、附件或本地构建语料提交进仓库。

## 2. 分支与提交

从最新 `main` 创建独立分支：

```powershell
git switch main
git pull --ff-only
git switch -c case/2025-example
```

分支命名：

- `case/<year>-<paper-code>`
- `knowledge/<topic>`
- `code/<topic>`
- `fix/<topic>`
- `docs/<topic>`

Commit 应小而完整，消息应说明意图，例如：

```text
case: add 2025 C problem decision card
knowledge: clarify small-sample model selection
fix: reject stale case indexes in validation
```

## 3. 新增或修改案例卡

案例卡必须使用 `templates/case-card-template.md` 的结构，并满足：

- `case_id`、`paper_id`、年份、题号和标题唯一；
- `source_page` 指向可核验的官方展示页；
- 正确填写 `evidence_mode`；
- 明确数据特点、核心问题和子问依赖；
- 不只列模型名称，必须写模型选择理由和替代方案；
- 将论文明确做法与贡献者建议分开；
- 给出验证证据、证据锚点和置信度；
- 提炼可迁移经验，并说明不能机械复制的部分；
- 使用原创转述，不粘贴大段摘要、正文、公式推导或图表。

修改案例卡后必须重建索引：

```powershell
python scripts/build_case_index.py --skill-root .
```

然后检查 `cases/index.json`、`cases/index.csv` 和 `cases/index.md` 的差异只包含预期变化。

## 4. 修改知识库

知识规则必须回答：

- 它解决什么决策问题；
- 适用的数据和假设是什么；
- 什么时候不应使用；
- 与替代方案相比的取舍是什么；
- 怎样验证；
- 哪些内容来自案例证据，哪些属于一般专家建议。

不得用模型出现频次证明模型优越，不得把相关关系写成因果结论，不得为了创新强行堆叠模型。

## 5. 修改代码

代码骨架应：

- 使用明确的数据接口和类型；
- 检查维度、缺失、单位、范围和约束可行性；
- 固定随机种子；
- 提供可运行的烟雾测试；
- 设置有意义的基线；
- 避免训练/测试泄漏；
- 不包含真实比赛答案、私人数据或本机路径。

## 6. 本地验证

```powershell
python -m pip install -r requirements-dev.txt
python scripts/validate_skill_content.py
python scripts/validate_repository.py
python scripts/search_cases.py "动态调度 随机故障 0-1规划" --top 3
Get-ChildItem code -Recurse -Filter *.py | ForEach-Object { python -B $_.FullName }
```

所有检查通过后再提交 PR。

## 7. Pull Request

PR 必须：

- 只解决一个清晰问题；
- 说明修改前的问题、修改方法和验证证据；
- 关联对应 Issue；
- 完成 PR 模板中的版权、来源、测试和授权确认；
- 通过全部自动检查；
- 解决审查意见；
- 获得 CODEOWNERS 批准。

维护者可以要求拆分、重写、补证据或拒绝不符合项目方向的贡献。合并通常使用 Squash Merge，以保持 `main` 历史清晰。

如果使用了 AI 辅助，请在 PR 中说明工具、用途、输入范围和人工核验方式。AI 输出不能作为事实来源；不得把原论文全文、私有仓库内容、访问凭据或无权披露的数据上传给外部 AI 服务。贡献者仍对 AI 辅助内容的准确性、原创性和权利负责。

## 8. 安全与敏感信息

发现密钥、访问令牌、私人数据或安全问题时，不要在普通 Issue 中公开。请按照 [SECURITY.md](SECURITY.md) 使用 GitHub 私有安全报告渠道。
