# 脚本说明

## 日常只读工具

| 脚本 | 用途 | 是否写文件 |
|---|---|---:|
| `search_cases.py` | 按问题结构检索案例卡 | 否 |
| `validate_skill_content.py` | 校验 Skill、案例、知识、模板和代码结构 | 否 |
| `validate_repository.py` | 校验仓库边界、链接、敏感内容和索引新鲜度 | 否 |

## 会修改生成内容的维护工具

| 脚本 | 用途 | 主要写入 |
|---|---|---|
| `build_case_index.py` | 从案例卡重建检索索引 | `cases/index.json`、`.csv`、`.md` |
| `synthesize_case_library.py` | 重新生成语料统计 | `knowledge/corpus-analysis.*` |
| `normalize_case_fields.py` | 规范案例卡字段 | 案例卡及其派生内容 |
| `draft_case_cards.py` | 从证据包生成案例草稿 | 指定草稿目录或案例文件 |
| `extract_paper_evidence.py` | 从本地合规语料生成紧凑证据包 | 本地构建目录 |

运行会写文件的脚本前必须：

1. 创建独立分支；
2. 保持工作树干净；
3. 记录输入语料版本和命令；
4. 完成后逐项检查 `git diff`；
5. 不提交原始 PDF、页面图片、OCR 缓存、抓取清单或本机路径；
6. 运行两个验证脚本和相关烟雾测试。

证据提取需要 `requirements-maintainer.txt`、Poppler/`pdftoppm` 和本地语料。该流程不是普通 Skill 运行依赖。
