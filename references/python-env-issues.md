# Python 环境冲突问题

## 问题描述

本机安装了 `uv`（Python 包管理工具），它设置了 `PYTHONHOME` 环境变量指向 Python 3.11：

```
PYTHONHOME=C:\Users\16673\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none
```

这会导致所有 Python 调用加载错误版本的库，出现类似以下错误：

```
ModuleNotFoundError: No module named 'sre_compile'
ImportError: SRE module mismatch
```

## 解决方案

### 每次运行前清除环境变量

```bash
# Git Bash
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME

# PowerShell
$env:PYTHONHOME=""; $env:UV_INTERNAL__PYTHONHOME=""
```

### 验证当前状态

```bash
# 检查 PYTHONHOME 是否被设置
echo $PYTHONHOME
echo $UV_INTERNAL__PYTHONHOME

# 如果有值，说明需要清除
```

## 影响范围

- 所有 Python 调用都会受影响
- 包括 `python`、`python3`、`pip`、`uv` 等命令
- 虚拟环境（.venv）中的 Python 也会受影响

## 为什么不用 conda？

用户之前尝试过 conda，但 conda 也有类似问题。使用 venv + 手动清除 PYTHONHOME 是最可靠的方案。
