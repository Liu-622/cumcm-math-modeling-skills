---
name: doctor
description: 环境检查与安装向导。手动触发，用于检查数学建模工作流在 Windows、macOS 或 Linux 上实际需要的解释器、编译器、绘图和 PDF 工具，并在用户明确同意后安装缺失项。
---

# Doctor 环境检查与安装向导

本 skill 只在用户显式触发时运行。先做只读检测并报告实际路径、版本和缺口；安装或修改系统前取得用户明确同意。不要把某个操作系统的命令交给另一平台，也不要因为可选工具缺失就把整个工作流判为不可用。

## 检查流程

1. 识别当前操作系统和 shell。Windows 原生会话使用 PowerShell；macOS/Linux 使用当前 POSIX shell。只有实际处于 Git Bash、WSL 等环境时才运行 Bash 命令。
2. 找到可用 Python 3 解释器。PowerShell 依次检查 `Get-Command python, py, python3 -ErrorAction SilentlyContinue`，并实际运行版本命令排除 Microsoft Store 占位符；POSIX 使用 `command -v python3 || command -v python`。后续统一使用已验证解释器的绝对路径或命令。
3. 使用本 skill 的跨平台检查脚本：

```text
python -X utf8 "<本 skill 实际路径>/scripts/check_environment.py"
```

如果 Python 不存在，先用本机原生命令检查其余工具，并将 Python 记为缺失；不能尝试运行 Python heredoc。
4. 根据本次选择的论文引擎和实际赛题功能判断必需项：

   - Python 3 是数据处理、求解和绘图阶段的基础依赖。
   - Typst 项目需要 `typst`；LaTeX 项目需要实际模板对应的编译器，中文 LaTeX 通常为 `xelatex`。二者不要求同时存在。
   - `numpy`、`pandas`、`matplotlib` 是常用基础包；`scipy`、`scikit-learn`、`openpyxl` 仅在模型、算法或附件格式需要时才成为必需。
   - DrawIO、`pdftoppm`、`mutool`、ImageMagick 是可选能力。已有等价流程图或 PDF 渲染工具时记录替代方案，不重复安装。
5. 输出表格，至少包含状态、工具/包、实际版本或路径、对当前任务的影响。未实际运行的检查标为 `UNVERIFIED`，不能记为通过。

## 安装处理

仅为当前任务真正缺失的能力给出命令。命令和包标识可能变化，执行前先用对应包管理器搜索或查官方安装说明核验；不要把示例包名当作永久有效事实。

- Windows：检测 `winget`、`scoop`、`choco`，优先使用用户已有的管理器。Python 包使用已验证解释器的 `-m pip install <包>`，避免 `pip` 指向另一解释器。
- macOS：检测 Homebrew；Python 包同样使用 `<python> -m pip`。
- Linux：读取 `/etc/os-release` 后选择实际发行版的管理器；不要默认系统一定使用 apt，也不要在未知发行版运行 `sudo`。

安装属于系统变更。列出将执行的精确命令、下载来源和大致影响后询问用户；用户明确同意后再执行。安装完成后重新运行同一检查，并实际编译一个最小文档或导入所需 Python 包，验证 PATH 和运行时已生效。

## Windows PowerShell 快速检查

没有 Python 时可先运行：

```powershell
$names = 'python','py','python3','typst','xelatex','drawio','pdftoppm','mutool','magick','winget','scoop','choco'
foreach ($name in $names) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) { "OK  $name  $($cmd.Source)" } else { "MISS $name" }
}
```

这段仅检查命令是否可发现；仍需运行版本或最小任务确认可执行文件真实可用。

## 结果边界

- 环境检查通过只说明工具可以启动，不证明论文、模型或图表正确。
- 编译器缺失时，写作可以继续，但最终 PDF 编译与视觉验收保持 `UNVERIFIED`。
- PDF 渲染工具缺失时，不能宣称视觉检查完成。
- 不安装与当前任务无关的完整工具链，也不因缺失单一可选工具阻塞已有替代方案。
