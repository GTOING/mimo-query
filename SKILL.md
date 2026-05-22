---
name: mimo-query
description: "Use when querying Xiaomi MiMo platform credits, managing MiMo accounts, or refreshing MiMo cookies. Multi-account CLI tool for platform.xiaomimimo.com with smart refresh workflow."
version: 2.2.0
author: User
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [mimo, xiaomi, credits, api, query, selenium, auto-refresh]
    related_skills: []
---

# MiMo Query — 小米 MiMo 平台多账号套餐查询

## Overview

查询和管理小米 MiMo 开放平台（platform.xiaomimimo.com）套餐信息的命令行工具集。

核心特性：**智能刷新机制** — 先查询检测问题，仅对 Cookie 过期的账号启动自动登录，跳过无法自动处理的错误（手机验证/频繁操作）。支持多账号并发查询、IMAP 邮箱验证码自动读取。

项目路径：`D:/mimo-query/`

## When to Use

- 用户询问 MiMo 平台套餐/额度/credits 用量
- 需要刷新 MiMo Cookie
- 需要添加/管理 MiMo 账号
- MiMo 查询返回 401 需要重新登录
- 需要配置 MiMo 定时查询任务

## ⚠️ PYTHONHOME 冲突（最重要）

本机 uv 的 Python 3.11 设置了 `PYTHONHOME` 环境变量，会污染所有 Python 调用。**每次运行任何命令前必须先清除**：

```bash
# Git Bash
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME

# PowerShell
$env:PYTHONHOME=""; $env:UV_INTERNAL__PYTHONHOME=""
```

## 环境要求

- Python 3.13（venv 路径：`D:/mimo-query/.venv/`）
- Google Chrome（auto_login.py 需要）
- 依赖已安装：`selenium`, `cryptography`, `webdriver-manager`

## 文件结构

```
D:/mimo-query/
├── .venv/                  # Python 3.13 虚拟环境（已装依赖）
├── mimo-query.py           # 套餐查询脚本（核心，零依赖，支持并发）
├── login.py                # 半自动 Cookie 抓取（零依赖）
├── auto_login.py           # 全自动登录 + Cookie 管理（需 selenium）
├── mimo-accounts.json      # 账号配置文件（加密存储）
└── README.md
```

## 标准工作流（智能刷新机制）

**核心原则**：先查询检测问题，仅对 Cookie 过期的账号启动自动登录，避免不必要的重复操作。

```
┌─────────────────────────────────────────────────────────┐
│  第一步：运行 mimo-query.py 检测所有账号                   │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 解析输出，分类账号状态：                              ││
│  │   ✓ 查询成功 → 记录结果，无需处理                     ││
│  │   ✗ Cookie 过期 (401) → 标记需要刷新                 ││
│  │   ✗ 跳过（无 Cookie） → 标记需要刷新                  ││
│  │   ✗ 手机验证 → 跳过，无法自动处理                     ││
│  │   ✗ 验证码过多 → 跳过，需等明天                       ││
│  │   ✗ 其他错误 → 跳过，记录错误信息                     ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  第二步：仅对需要刷新的账号运行 auto_login.py              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ auto_login.py -a "账号1,账号2,..."                   ││
│  │                                                     ││
│  │ 自动处理：                                           ││
│  │   • 打开 Chrome → 填写账号密码 → 勾选协议 → 登录      ││
│  │   • 如需邮箱验证：IMAP 自动读取验证码 → 自动填入       ││
│  │   • 登录成功后自动抓取 Cookie 保存                    ││
│  │                                                     ││
│  │ 异常处理：                                           ││
│  │   • 需要手机验证码 → 跳过该账号                       ││
│  │   • 验证码发送过多 → 跳过，提示等明天                  ││
│  │   • 浏览器异常 → 自动关闭，不堆积窗口                 ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  第三步：再次运行 mimo-query.py 获取最终结果              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 并发查询所有账号（ThreadPoolExecutor，最多 5 线程）    ││
│  │ 按配置文件顺序输出结果                                ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  第四步：格式化输出 + 详细分析总结                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 1. 整理为清晰的表格，包含：                           ││
│  │    • 各账号套餐、额度、已用、百分比、有效期            ││
│  │    • 刷新结果摘要（成功/失败/跳过）                    ││
│  │                                                     ││
│  │ 2. 详细分析总结（见下方"查询分析报告"章节）            ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

## 查询历史记录（JSON 日志）

每次查询后，使用 `--save-history` 参数将结果自动保存到本地 JSON 文件，供下次查询做对比分析。

### 历史文件

- 路径：`D:/mimo-query/mimo-history.json`
- 格式：JSON 数组，每条记录包含时间戳和各账号数据
- 保留最近 50 条记录（自动裁剪）

### 记录格式

```json
{
  "timestamp": "2026-05-22 12:26:03",
  "accounts": {
    "账号名": {
      "plan": "Pro",
      "quota": 700000000,
      "used": 60125118,
      "expires": "2026-06-19",
      "auto_renew": false
    }
  }
}
```

### 第三步（续）：保存查询结果到历史

在第三步查询完成后，使用 `--save-history` 参数再次运行（或直接用带该参数的命令查询）。该参数用于配置文件账号查询流程；直接传 Cookie 的单账号模式不保存历史。

```bash
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME && \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/mimo-query.py --save-history
```

> 如果第三步已经用 `--save-history` 查询，则无需重复执行。

### 第四步：读取历史记录生成分析报告

在生成分析报告前，读取历史文件获取上次查询数据：

```bash
# 读取倒数第二条记录（上次查询）用于对比
# 如果只有 1 条记录，说明是首次查询，无历史对比数据
```

**历史文件读取方式**：用 `read_file` 工具读取 `D:/mimo-query/mimo-history.json`，解析 JSON 数组：
- `history[-1]` = 本次查询（刚保存的）
- `history[-2]` = 上次查询（用于对比）
- 如果数组长度 < 2，标注"首次查询，无历史对比数据"

**对比计算**：
- 时间间隔 = 本次 timestamp - 上次 timestamp（小时）
- 各账号增量 = 本次 used - 上次 used
- 每小时消耗 = 增量 / 时间间隔

## ⚠️ 执行完整性要求（必须遵守）

当用户要求"执行查询skill"或触发此 skill 时，**必须严格执行上述四步工作流的每一步**，尤其是第四步的详细分析报告。不得跳过任何步骤。

常见错误：
- ❌ 只运行脚本不生成分析报告
- ❌ 只输出原始数据不整理为表格
- ❌ 跳过用量对比、消耗趋势、剩余时间预估
- ❌ 不保存查询历史（必须用 --save-history）

## 查询分析报告

每次查询完成后，必须生成详细的分析总结，包含以下内容：

### 1. 用量对比（与上次查询）
- 各账号**本次已用** vs **上次已用**的差值（+X 万）
- 标注消耗最多的账号

### 2. 每小时消耗量
- 计算两次查询之间的**时间间隔**（小时）
- 计算各账号的**每小时消耗量** = 增量 / 时间间隔
- 公式：`每小时消耗 = (本次已用 - 上次已用) / 间隔小时数`

### 3. 消耗趋势分析
- 根据每小时消耗量判断趋势：
  - 📈 **上升趋势**：当前消耗 > 上次查询时的每小时消耗
  - 📉 **下降趋势**：当前消耗 < 上次查询时的每小时消耗
  - ➡️ **平稳**：消耗量基本持平
- 如果是首次查询或无历史数据，标注"无历史对比数据"

### 4. 剩余使用时间预估
- **单账号预估**：`剩余额度 / 每小时消耗 = 预计可用小时数`
- **总余额预估**：所有账号总余额 / 总每小时消耗
- 如果消耗为 0，显示"当前无消耗，无法预估"
- 注意：这只是线性预估，实际使用可能有波动

### 5. 汇总建议
- 哪些账号消耗较快需要关注
- 是否需要提前续费提醒
- Cookie 状态异常的账号提醒

### 示例输出格式

```
📊 用量分析报告

▸ 与上次查询对比（3.2小时前）
  • xqh***：↑ 104万（每小时约32万）
  • gem***：↑ 98万（每小时约30万）
  • 191***：↑ 29万（每小时约9万）
  • 297***：↑ 153万（每小时约48万）

▸ 消耗趋势
  • 297***：📈 上升（上次每小时约20万 → 本次48万）
  • xqh***：➡️ 平稳
  • gem***：➡️ 平稳
  • 191**：📉 下降

▸ 剩余使用时间预估（按当前消耗速率）
  • xqh***：约 794小时（~33天）
  • gem***：约 832小时（~35天）
  • 191***：约 3,203小时（~133天）
  • 297***：约 603小时（~25天）⚠️
  • 总余额预估：约 534小时（~22天）

▸ 关注提醒
  • ⚠️ 297*** 消耗较快，建议关注
  • ⚠️ gem*** 仍需手动手机验证
```

## 快速命令

### 完整智能流程（推荐）

```bash
# 1. 检测问题账号
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME && \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/mimo-query.py

# 2. 仅刷新过期账号（根据第一步结果）
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME && \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/auto_login.py -a "过期账号1,过期账号2"

# 3. 再次查询获取最终结果 + 保存历史
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME && \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/mimo-query.py --save-history
```

### 一键命令（组合）

```bash
# 检测 + 刷新 + 查询（智能模式，自动跳过有效的）+ 保存历史
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME && \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/auto_login.py && \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/mimo-query.py --save-history
```

> **Shell 变量简写**：`MIMO_PY="unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME && D:/mimo-query/.venv/Scripts/python.exe"`

### PowerShell 命令

```powershell
# 检测问题账号
$env:PYTHONHOME=""; $env:UV_INTERNAL__PYTHONHOME=""; \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/mimo-query.py

# 刷新指定账号
$env:PYTHONHOME=""; $env:UV_INTERNAL__PYTHONHOME=""; \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/auto_login.py -a "过期账号1,过期账号2"
```

## auto_login.py 详解

### 智能刷新（默认行为）

直接运行 `auto_login.py`（不加参数）时：
1. 自动检查所有账号的 Cookie 有效性（通过 API 验证）
2. 只刷新无效/过期的账号
3. 有效账号自动跳过

```
发现 1 个账号需要刷新:
  ✗ 测试账号 — Cookie 已过期

[测试账号] 自动登录...
  ✓ Cookie 已更新

完成：1/1 个账号更新成功
```

### 命令参数

| 参数 | 说明 |
|------|------|
| （无参数） | 智能刷新：只刷新过期 Cookie |
| `--add` | 添加/更新账号（交互式输入） |
| `--show` | 显示所有账号信息（解密后明文） |
| `--check` | 检查所有 Cookie 有效性 |
| `-a "名称"` | 刷新指定账号（逗号分隔支持多个） |
| `--all` | 强制刷新所有账号（忽略有效性） |
| `--timeout 180` | 验证码等待超时秒数（默认 120） |

### 自动登录流程

```
[主账号] 自动登录...
  打开登录页...
  填写账号: 138***
  填写密码...
  已勾选用户协议
  点击登录...
  检测到安全验证页，自动点击发送邮件...
  验证邮件已发送！
  等待验证邮件到达（15秒）...
  通过 IMAP 自动读取验证码...
  连接邮箱 imap.163.com...
  IMAP 登录成功
  检查: 小米账号登录验证
  获取验证码成功: 971891
  验证码已自动填入: 971891
  已自动提交验证码
  登录成功！正在抓取 Cookie...
[主账号] ✓ Cookie 已更新
```

### 异常处理

| 情况 | 处理方式 |
|------|----------|
| 不需要验证码 | 直接登录，自动抓取 Cookie |
| 需要邮箱验证码 | 自动发送邮件 → IMAP 读取 → 自动填入 |
| 需要手机验证码 | 跳过该账号，提示"需要手机验证码，无法自动处理" |
| 验证码发送过多 | 跳过该账号，提示"验证码发送过多，请明天再试" |
| 浏览器异常 | 自动关闭浏览器，不堆积窗口 |

## mimo-query.py 详解

### 输出字段

| 字段 | 含义 |
|------|------|
| 查询时间 | 本次查询时间戳 |
| 账号 | 账号标签名（多账号时显示） |
| 套餐 | 当前套餐（Pro / Free 等） |
| 额度 | 总 Credits 额度 |
| 已用 | 已使用额度和百分比 |
| 有效期至 | 计费周期结束时间 |
| 自动续费 | 是否开启 |

### 输出解析

查询时脚本会输出以下几种情况：

```
# 成功
=== 主账号 ===
查询时间   2026-05-21 10:30:15
套餐       Pro
额度       700,000,000 Credits
已用       21,293,523（3.0%）
有效期至   2026-06-19 23:59:59
自动续费   关闭

# 跳过（无 Cookie）
=== 测试账号 ===
跳过: Cookie 未获取，请运行 auto_login.py

# 错误（Cookie 过期，输出到 stderr）
错误: API error code 401
```

**智能刷新判断依据**：
- 包含 "跳过" → 无 Cookie，需要刷新
- 包含 "401" 或 "unauthorized" → Cookie 过期，需要刷新
- 其他错误 → 跳过，记录错误信息

## 账号管理

### 添加账号（--add）

```bash
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME && \
  D:/mimo-query/.venv/Scripts/python.exe D:/mimo-query/auto_login.py --add
```

交互式输入：
- 账号名称（自定义标签）
- 手机号/邮箱（小米账号登录名）
- 密码（加密存储）
- 邮箱地址 + IMAP 授权码（可选，用于自动读取验证码）

### 配置文件格式

`mimo-accounts.json`（与脚本同目录）：

```json
[
  {
    "label": "主账号",
    "cookie": "api-platform_slh=xxx; ...",
    "username": "加密后的用户名",
    "password": "加密后的密码",
    "email": "加密后的邮箱",
    "email_pass": "加密后的授权码",
    "email_imap": "imap.163.com"
  }
]
```

- `mimo-query.py` 只读取 `cookie` 和 `label`
- 敏感字段使用本机硬件 ID 加密（Fernet + PBKDF2），仅本机可解密

## 邮箱 IMAP 配置

| 邮箱 | IMAP 服务器 | 特殊处理 |
|------|------------|----------|
| 163.com | `imap.163.com` | 需要授权码（非登录密码），登录前自动发 ID 命令 |
| 126.com | `imap.126.com` | 需要授权码（非登录密码），登录前自动发 ID 命令 |
| qq.com / foxmail.com | `imap.qq.com` | 需要授权码 |
| gmail.com | `imap.gmail.com` | 需要两步验证 + 应用专用密码 |
| outlook / hotmail | `outlook.office365.com` | — |

## 定时任务集成

可用 Hermes cron 定时执行智能刷新、查询和历史记录保存流程。

### 快速配置

```bash
# 每天早上 9 点智能刷新 + 查询 + 保存历史
hermes cron create \
  --name "mimo-daily-query" \
  --schedule "0 9 * * *" \
  --prompt "严格按照已加载的 mimo-query skill 执行完整的四步智能刷新工作流。不得跳过任何步骤，尤其是第四步的详细分析报告。" \
  --deliver "telegram" \
  --toolsets "terminal"
```

## 安装依赖

```bash
# ⚠️ 必须先清除 PYTHONHOME
unset PYTHONHOME && unset UV_INTERNAL__PYTHONHOME

# 用 venv 的 python 安装
D:/mimo-query/.venv/Scripts/python.exe -m pip install selenium cryptography webdriver-manager
```

## Common Pitfalls

1. **PYTHONHOME 污染**（最重要）— uv 的 Python 3.11 设置了 PYTHONHOME，导致所有 Python 调用加载错误版本的库 → 每次运行前必须先清除环境变量
2. **`python3` 命令在 Windows 上失败**（exit code 49，Windows Store 重定向）→ 必须用 venv 的 python 路径
3. **Cookie 有效期有限** → 失效后运行 `auto_login.py` 刷新（默认只刷新过期的）
4. **IMAP 连接报 "Unsafe Login"** → 必须用授权码，不是登录密码
5. **selenium 报错找不到 Chrome** → 确保 Chrome 已安装，或安装 `webdriver-manager`
6. **查询返回 401** → Cookie 失效，需要重新登录
7. **验证码发送过多** → 小米平台限制频率，需等明天再试
8. **login.py 更新 Cookie 后 auto_login.py 无法刷新** — 已修复，login.py 只更新 cookie 字段，保留 username/password/email

## Verification Checklist

- [ ] `mimo-query.py` 能正常查询并输出套餐信息
- [ ] `mimo-accounts.json` 中有有效的 cookie 字段
- [ ] 如需自动登录，`selenium` 和 `cryptography` 已安装
- [ ] Chrome 浏览器已安装（auto_login.py 需要）
- [ ] PYTHONHOME 冲突已处理（每次运行前清除）
- [ ] `mimo-query.py --save-history` 能正常写入 `mimo-history.json`
- [ ] `mimo-history.json` 中至少有 1 条记录（首次查询无对比，2 条以上可做对比分析）
