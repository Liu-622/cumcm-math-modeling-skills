# 数学建模竞赛专家 Skill Pro

[![Validate](https://github.com/skillforCUMCM/math-modeling-skill-pro/actions/workflows/validate.yml/badge.svg)](https://github.com/skillforCUMCM/math-modeling-skill-pro/actions/workflows/validate.yml)

这是 `skillforCUMCM` 组织维护的数学建模竞赛专家 Skill 私有主仓库，用于保存、审查和发布完整版内容。

> 仓库等级：**Private / Pro**。未经项目所有者明确许可，不得公开、转售、镜像、重新打包或将仓库内容转移到公共仓库。

## 项目目标

把历年公开优秀论文中的建模决策提炼为可检索、可验证、可复用的问题解决能力，帮助使用者完成：

- 赛题理解与子问题依赖分析；
- 问题类型判断与结构化案例检索；
- 稳妥、高分、创新三类候选方案比较；
- 变量、参数、目标函数、约束和机理方程设计；
- 算法、代码与结果输出规划；
- 误差、敏感性、稳健性和对比验证；
- 创新点与论文结构设计。

## 当前内容

- 139 张 CUMCM 结构化案例卡，覆盖 2012—2025 年；
- 10 份核心知识文档和 1 份语料统计数据；
- 6 份分析与写作模板；
- 8 类可运行代码骨架；
- 案例索引、结构检索与内容验证脚本；
- Skill 入口文件和 Codex 界面配置。

本仓库不保存原论文 PDF、页面图片、附件或 OCR 缓存。来源、证据模式和复核边界见 [语料来源说明](references/corpus-provenance.md) 与 [第三方来源说明](THIRD-PARTY-NOTICE.md)。

## 目录

| 路径 | 用途 |
|---|---|
| `SKILL.md` | Skill 的角色、工作流、决策规则和输出契约 |
| `cases/` | 案例卡与 JSON/CSV/Markdown 索引 |
| `knowledge/` | 问题类型、模型选择、组合、验证、创新和写作知识 |
| `templates/` | 问题分析、模型设计、验证、论文和案例卡模板 |
| `code/` | 预测、评价、优化、聚类、机器学习、网络、机理和仿真骨架 |
| `scripts/` | 检索、索引、规范化、提取、综合和验证工具 |
| `references/` | 语料来源、覆盖、OCR 与版权边界 |
| `.github/` | PR、Issue、CODEOWNERS、Actions 和依赖更新配置 |
| `docs/` | 仓库治理和审查清单 |

## 本地开始

```powershell
git clone https://github.com/skillforCUMCM/math-modeling-skill-pro.git
cd math-modeling-skill-pro
python -m pip install -r requirements-dev.txt
python scripts/validate_skill_content.py
python scripts/validate_repository.py
python scripts/search_cases.py "小样本 多指标 综合评价 稳健性" --top 6
```

只有在维护原始证据提取流程时，才需要额外安装：

```powershell
python -m pip install -r requirements-maintainer.txt
```

OCR 维护流程还需要本机安装 Poppler，并确保 `pdftoppm` 可用；普通 Skill 使用、案例检索和 CI 不需要 OCR 工具链。

运行全部代码骨架烟雾测试：

```powershell
Get-ChildItem code -Recurse -Filter *.py | ForEach-Object { python -B $_.FullName }
```

## 协作流程

```text
Issue / Discussion
        ↓
创建独立分支
        ↓
修改案例、知识、模板或代码
        ↓
本地运行验证
        ↓
Pull Request
        ↓
自动检查 + CODEOWNERS 审核
        ↓
合并到 main
```

禁止直接向 `main` 推送。分支建议使用：

- `case/<year>-<paper-code>`：新增或重构案例卡；
- `knowledge/<topic>`：知识库修改；
- `code/<topic>`：代码骨架修改；
- `fix/<topic>`：错误修复；
- `docs/<topic>`：文档和治理修改。

完整贡献规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。提交 PR 即表示贡献者确认已阅读 [贡献授权约定](CONTRIBUTOR-AGREEMENT.md)。

## 版本与发行

- `main` 始终代表已经审核、可构建的 Pro 正式内容；
- 功能分支只保存待审修改；
- 发行版本使用 `vX.Y.Z` 标签；
- 公共体验版从经过审查的白名单内容单独构建，不直接把本仓库改为公开；
- 原始语料、构建缓存和商业交付文件不进入 Git 历史。

## 重要边界

- 本项目为独立制作的辅助工具，不代表赛事组委会或来源网站；
- 案例卡是对建模决策的结构化转述，不是论文原文库；
- 历史案例用于结构类比，不构成某模型普遍优越的证明；
- AI、模型、公式、代码和结论均需由使用者复核；
- 参赛使用须遵守具体赛事、学校和团队规则。
