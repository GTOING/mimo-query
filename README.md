# MiMo Query — 小米 MiMo 平台多账号套餐查询工具

一套用于查询和管理小米 MiMo 开放平台（platform.xiaomimimo.com）套餐信息的命令行工具集。

支持多账号管理、自动登录、Cookie 自动抓取、邮箱验证码自动读取、Cookie 有效性检查、并发查询。

---

## 目录

- [项目文件说明](#项目文件说明)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [脚本一：mimo-query.py（套餐查询）](#脚本一mimo-querypy套餐查询)
- [脚本二：login.py（半自动 Cookie 抓取）](#脚本二loginpy半自动-cookie-抓取)
- [脚本三：auto_login.py（全自动登录 + Cookie 管理）](#脚本三auto_loginpy全自动登录--cookie-管理)
- [配置文件说明](#配置文件说明)
- [加密方式](#加密方式)
- [完整使用流程](#完整使用流程)
- [常见问题](#常见问题)

---

## 项目文件说明

```
mimo-query/
├── mimo-query.py          # 套餐查询脚本（核心工具）
├── login.py               # 半自动 Cookie 抓取（浏览器表单粘贴）
├── auto_login.py          # 全自动登录 + Cookie 管理（Selenium + IMAP）
├── mimo-accounts.json     # 账号配置文件（自动生成，存储 Cookie 和凭据）
├── requirements.txt       # Python 依赖
└── README.md              # 本文档
```

| 脚本 | 功能 | 依赖 | 适用场景 |
|------|------|------|----------|
| `mimo-query.py` | 查询套餐用量（并发） | 无（纯标准库） | 日常查询 |
| `login.py` | 打开浏览器登录页，手动粘贴 Cookie 保存 | 无（纯标准库） | 首次获取 Cookie |
| `auto_login.py` | 自动登录 + Cookie 检查/刷新 + 账号管理 | selenium, cryptography | Cookie 管理 |

---

## 环境要求

- **操作系统**：macOS / Linux / Windows（密码加密使用各平台原生机器 ID）
- **Python**：3.10+
- **浏览器**：Google Chrome（auto_login.py 需要）
- **邮箱**：163 / 126 / QQ / Foxmail / Gmail / Outlook 等支持 IMAP 的邮箱（用于自动读取验证码）

---

## 快速开始

### 第一步：创建虚拟环境（推荐）

```bash
cd mimo-query
conda create -n mimo python=3.13 -y
conda activate mimo
pip install -r requirements.txt
pip install webdriver-manager  # 可选：系统没有 chromedriver 时自动下载
```

> 如果不用 conda，也可以用 venv：
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate
> pip install -r requirements.txt
> ```

### 第二步：添加账号

```bash
python3 auto_login.py --add
```

### 第三步：自动登录获取 Cookie

```bash
python3 auto_login.py
```

脚本会自动：
1. 打开 Chrome 浏览器
2. 填写账号密码
3. 勾选用户协议
4. 点击登录
5. 如果需要邮箱验证：自动发送邮件 → 通过 IMAP 读取验证码 → 自动填入
6. 登录成功后自动抓取 Cookie 保存到配置文件
7. 登录完成后自动关闭浏览器

### 第四步：查询套餐

```bash
python3 mimo-query.py
```

输出示例：
```
=== 主账号 ===
查询时间   2026-05-21 10:30:15
套餐       Pro
额度       700,000,000 Credits
已用       21,293,523（3.0%）
有效期至   2026-06-19 23:59:59
自动续费   关闭

=== 备用账号 ===
查询时间   2026-05-21 10:30:15
套餐       Free
额度       1,000,000 Credits
已用       500,000（50.0%）
...
```

---

## 脚本一：mimo-query.py（套餐查询）

查询 MiMo 平台套餐用量，支持多账号**并发查询**。**零依赖**，仅用 Python 标准库。

多账号查询时自动使用线程池并发（最多 5 个线程），结果按配置文件顺序输出。

### 用法

```bash
# 查询所有账号（有配置文件时默认行为）
python3 mimo-query.py

# 查询指定账号
python3 mimo-query.py -a "主账号"

# 强制查询所有账号
python3 mimo-query.py --all

# 使用自定义配置文件
python3 mimo-query.py -c /path/to/config.json

# 直接传 Cookie（单账号模式，向后兼容）
python3 mimo-query.py 'api-platform_slh=xxx; api-platform_ph=xxx; ...'

# 通过环境变量
MIMO_COOKIE='api-platform_slh=xxx; ...' python3 mimo-query.py
```

### 输出字段说明

| 字段 | 含义 |
|------|------|
| 查询时间 | 本次查询的时间戳 |
| 账号 | 账号标签名（多账号时显示） |
| 套餐 | 当前套餐名称（如 Pro、Free） |
| 额度 | 总 Credits 额度 |
| 已用 | 已使用额度和百分比 |
| 有效期至 | 当前计费周期结束时间 |
| 自动续费 | 是否开启自动续费 |
| 状态 | 仅在已过期时显示 |

### 无 Cookie 的账号

如果配置文件中某个账号没有 Cookie（登录失败或未配置），查询时会跳过并显示原因：

```
=== 账号B ===
跳过: Cookie 未获取，请运行 auto_login.py
```

只有所有账号都跳过时才返回错误码。

---

## 脚本二：login.py（半自动 Cookie 抓取）

打开浏览器登录页和本地表单页，手动粘贴 Cookie 保存。**零依赖**。

> 注意：使用 login.py 更新 Cookie 时，会保留账号的 username、password、email 等已有字段，不会丢失。

### 用法

```bash
python3 login.py
```

### 流程

1. 自动打开浏览器 MiMo 登录页
2. 同时打开本地表单页 `http://127.0.0.1:<端口>/`
3. 在 MiMo 登录页登录后，从 DevTools 复制 Cookie
4. 粘贴到本地表单页，点击提交
5. 脚本自动解析 Cookie、验证有效性、保存到配置文件

### 如何获取 Cookie

1. 浏览器登录 `platform.xiaomimimo.com`
2. 按 `F12` 打开 DevTools
3. 切到 `Application` → `Cookies` → `platform.xiaomimimo.com`
4. 右键表格 → `Select All`，再右键 → `Copy` → `Copy all cookies as string`
5. 粘贴到本地表单页

> 也可以从 `Network` 标签里复制任意请求的 `Cookie` 请求头。

### 支持的 Cookie 格式

- **Chrome DevTools 表格格式**（Tab 分隔，直接从 Cookies 面板复制）
- **标准 Cookie 字符串**（`key=value; key=value` 格式）

按 `Ctrl+C` 退出。

---

## 脚本三：auto_login.py（全自动登录 + Cookie 管理）

使用 Selenium 自动填写账号密码，通过 IMAP 自动读取邮箱验证码，自动抓取 Cookie 保存。

支持 Cookie 有效性检查、选择性刷新、多账号批量操作。

**需要安装依赖**：`selenium`、`cryptography`（`webdriver-manager` 可选）

### 用法总览

```bash
# 添加/更新账号（交互式输入）
python3 auto_login.py --add

# 显示所有账号信息（解密）
python3 auto_login.py --show

# 检查所有 Cookie 有效性
python3 auto_login.py --check

# 只刷新过期的 Cookie（默认行为，智能跳过有效账号）
python3 auto_login.py

# 刷新指定账号（逗号分隔支持多个）
python3 auto_login.py -a "主账号"
python3 auto_login.py -a "主账号,备用账号"

# 强制刷新所有账号（不管是否过期）
python3 auto_login.py --all

# 设置验证等待超时（默认 120 秒）
python3 auto_login.py --timeout 180
```

### --add 添加账号

运行后按提示输入：

```
账号名称（如：主账号）: 主账号
手机号/邮箱: 13800138000
密码（输入不可见）: ********

邮箱 IMAP 配置（用于自动读取验证码，可跳过）
邮箱地址（如 xxx@163.com，跳过直接回车）: xxx@163.com
邮箱授权码（非登录密码，在邮箱设置→IMAP中获取）: ********
IMAP 服务器（默认自动识别，直接回车）:
```

- **账号名称**：自定义标签，用于 `--account` 参数
- **手机号/邮箱**：小米账号登录名
- **密码**：小米账号密码（输入时不可见，加密存储）
- **邮箱地址**：接收验证码的邮箱（可跳过，跳过后需手动输入验证码）
- **邮箱授权码**：IMAP 专用密码（不是邮箱登录密码，加密存储）
- **IMAP 服务器**：自动识别，无需手动输入

### --show 查看账号信息

```bash
python3 auto_login.py --show
```

输出示例（密码和授权码为解密后的明文）：
```
────────────────────────────────────────
账号: 主账号
用户名: 13800138000
密码: xiaomi_password_123
邮箱: xxx@163.com
邮箱授权码: IMAXXXXXXXAUTHCODE
IMAP: imap.163.com
Cookie: ✓ 已有（320 字符）
────────────────────────────────────────
账号: 备用账号
用户名: user@gmail.com
密码: gmail_password_456
邮箱: user@gmail.com
邮箱授权码: XXXX XXXX XXXX XXXX
IMAP: imap.gmail.com
Cookie: ✗ 未获取，运行 auto_login.py 可自动刷新
────────────────────────────────────────
```

### --check 检查 Cookie 有效性

```bash
python3 auto_login.py --check
```

通过调用 MiMo API 验证每个账号的 Cookie 是否有效：

```
✓ 有效（2 个）:
  主账号 — Pro
  备用账号 — Free

✗ 无效（1 个）:
  测试账号 — Cookie 已过期
```

### 默认行为：智能刷新

直接运行 `python3 auto_login.py`（不加参数）时：

1. 自动检查所有账号的 Cookie 有效性
2. 只刷新无效/过期的账号
3. 有效账号自动跳过

```
发现 1 个账号需要刷新:
  ✗ 测试账号 — Cookie 已过期

[测试账号] 自动登录...
  ...
[测试账号] ✓ Cookie 已更新

完成：1/1 个账号更新成功
```

如果所有 Cookie 都有效：
```
所有账号 Cookie 有效，无需刷新
```

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

### 自动处理的异常情况

| 情况 | 处理方式 |
|------|----------|
| 不需要验证码 | 直接登录，自动抓取 Cookie |
| 需要邮箱验证码 | 自动发送邮件 → IMAP 读取 → 自动填入 |
| 需要手机验证码 | 跳过该账号，提示"需要手机验证码，无法自动处理" |
| 验证码发送过多 | 跳过该账号，提示"验证码发送过多，请明天再试" |
| 浏览器管理 | 登录成功/失败后自动关闭浏览器，不堆积窗口 |

### IMAP 自动识别

`--add` 时输入邮箱地址，自动识别 IMAP 服务器：

| 邮箱 | IMAP 服务器 | 特殊处理 |
|------|------------|----------|
| `qq.com` / `vip.qq.com` | `imap.qq.com` | — |
| `foxmail.com` | `imap.qq.com` | — |
| `163.com` / `vip.163.com` | `imap.163.com` | 自动发送 ID 命令 |
| `126.com` | `imap.163.com` | 自动发送 ID 命令 |
| `gmail.com` | `imap.gmail.com` | 需要应用专用密码 |
| `outlook` / `hotmail` | `outlook.office365.com` | — |
| 其他 | 提示手动输入 | — |

---

## 配置文件说明

配置文件路径：`mimo-accounts.json`（与脚本同目录）

### 文件格式

```json
[
  {
    "label": "主账号",
    "cookie": "api-platform_slh=xxx; api-platform_ph=xxx; api-platform_serviceToken=xxx; userId=xxx",
    "username": "加密后的用户名",
    "password": "加密后的密码",
    "email": "加密后的邮箱地址",
    "email_pass": "加密后的邮箱授权码",
    "email_imap": "imap.163.com"
  },
  {
    "label": "备用账号",
    "cookie": "...",
    "username": "加密后的用户名",
    "password": "加密后的密码"
  }
]
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `label` | 是 | 账号标签名，用于 `--account` 参数 |
| `cookie` | 否 | 登录后的 Cookie（由 auto_login.py 自动填充） |
| `username` | 否 | 加密存储的小米账号（由 `--add` 生成） |
| `password` | 否 | 加密存储的小米密码（由 `--add` 生成） |
| `email` | 否 | 加密存储的邮箱地址（由 `--add` 生成） |
| `email_pass` | 否 | 加密存储的邮箱授权码（由 `--add` 生成） |
| `email_imap` | 否 | IMAP 服务器地址（明文） |

> `mimo-query.py` 查询时只读取 `cookie` 和 `label`，忽略其他字段。
> `login.py` 更新 Cookie 时保留所有已有字段，不会覆盖 username/password 等。

---

## 完整使用流程

### 场景一：首次使用

```bash
# 1. 创建环境
conda create -n mimo python=3.13 -y
conda activate mimo
pip install -r requirements.txt

# 2. 添加账号
python3 auto_login.py --add

# 3. 自动登录获取 Cookie
python3 auto_login.py

# 4. 查询套餐
python3 mimo-query.py
```

### 场景二：添加更多账号

```bash
conda activate mimo

# 添加新账号
python3 auto_login.py --add

# 只登录新账号
python3 auto_login.py -a "新账号"

# 查询所有账号
python3 mimo-query.py
```

### 场景三：Cookie 过期后刷新

```bash
conda activate mimo

# 先检查哪些过期了
python3 auto_login.py --check

# 只刷新过期的（默认行为，自动跳过有效账号）
python3 auto_login.py

# 或只刷新指定的
python3 auto_login.py -a "主账号,备用账号"

# 查询
python3 mimo-query.py
```

### 场景四：强制刷新所有账号

```bash
python3 auto_login.py --all
```

### 场景五：不想用 Selenium（手动模式）

```bash
# 用 login.py 手动粘贴 Cookie（不会覆盖已有的加密凭据）
python3 login.py

# 查询
python3 mimo-query.py
```

### 场景六：查看账号配置

```bash
# 查看解密后的账号信息
python3 auto_login.py --show

# 检查 Cookie 有效性
python3 auto_login.py --check
```

---

## 常见问题

### Q: 运行 auto_login.py 报错 `No module named 'selenium'`

需要先安装依赖：
```bash
conda activate mimo
pip install -r requirements.txt
```

### Q: chromedriver 版本不匹配

脚本优先使用系统 chromedriver，失败时尝试 webdriver-manager 自动下载。如果都不行：
```bash
pip install webdriver-manager
```
或手动下载匹配版本的 chromedriver 放入 PATH。

### Q: 浏览器打开后堆积了很多窗口

已修复。现在登录成功/失败后会自动关闭浏览器，不再堆积。

### Q: IMAP 连接 163/126 邮箱报错 "Unsafe Login"

需要使用**客户端授权密码**，不是邮箱登录密码：
1. 登录 163 邮箱网页版
2. 设置 → POP3/SMTP/IMAP
3. 开启 IMAP 服务
4. 点击「新增授权密码」，生成专用密码
5. 用这个授权密码重新运行 `--add`

### Q: Gmail IMAP 不支持

Gmail 需要开启**两步验证**后生成**应用专用密码**：
1. 打开 https://myaccount.google.com/security
2. 开启两步验证
3. 搜索"应用专用密码"，生成新密码
4. 用生成的 16 位密码作为 IMAP 授权码

### Q: 读到了旧的验证码

脚本会在点击"发送邮件"后等待 15 秒再读取邮箱。如果仍然读到旧邮件，可能是邮箱延迟较大，可以手动在浏览器中输入验证码。

### Q: 某个账号显示"需要手机验证码，无法自动处理"

该账号的安全验证绑定的是手机号而非邮箱，脚本无法自动处理。会自动跳过该账号，其他账号不受影响。

### Q: 某个账号显示"验证码发送过多，请明天再试"

小米平台对验证码发送有频率限制。该账号当天无法再发送验证码，需等明天。其他账号不受影响。

### Q: 查询时显示"跳过: Cookie 未获取"

该账号的 Cookie 还未获取或已失效。运行 `python3 auto_login.py` 刷新即可（会自动跳过 Cookie 有效的账号）。

### Q: 用 login.py 手动粘贴 Cookie 后，auto_login.py 无法自动刷新了

已修复。login.py 更新 Cookie 时只更新 `cookie` 字段，保留 `username`、`password`、`email` 等已有字段。

### Q: 配置文件在哪里

与脚本同目录下的 `mimo-accounts.json`。可以用 `--config` 参数指定其他路径：
```bash
python3 mimo-query.py -c /path/to/config.json
```

### Q: 密码安全吗

`--add` 输入的密码使用本机硬件 ID 派生的密钥加密存储（Fernet + PBKDF2），仅本机可解密。使用 `--show` 可查看解密后的明文。

### Q: 可以不用 conda 吗

可以，任何 Python 虚拟环境都行：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

查询脚本 `mimo-query.py` 和半自动脚本 `login.py` 不需要任何依赖，可以直接用系统 Python 运行。

### Q: Windows / Linux 可以用吗

可以。三个脚本均支持 macOS / Linux / Windows。密码加密使用各平台原生机器 ID：

| 平台 | 密钥来源 |
|------|----------|
| macOS | IOPlatformUUID |
| Linux | /etc/machine-id |
| Windows | BIOS UUID |
| 回退 | hostname + username |

---

## Cookie 生命周期

MiMo 平台的 Cookie 在以下情况下会失效：

- 用户主动退出登录
- 在浏览器中切换小米账号
- Cookie 过期（通常数天到数周）

**推荐维护方式**：

```bash
# 定期检查 Cookie 状态
python3 auto_login.py --check

# 只刷新过期的（自动跳过有效的）
python3 auto_login.py
```

---

## 加密方式

敏感字段（username、password、email、email_pass）使用 Fernet 对称加密存储。

加密流程：
```
机器唯一 ID (machine_id)
        ↓
PBKDF2-HMAC-SHA256
  ├─ salt: "mimo-query-salt"
  ├─ iterations: 100,000
  └─ output: 32 字节密钥
        ↓
  base64 URL-safe 编码
        ↓
Fernet 对称加密 (AES-128-CBC + HMAC-SHA256)
        ↓
  base64 密文 → 存入 JSON
```

各平台机器 ID 来源：

| 平台 | 来源 |
|------|------|
| macOS | IOPlatformUUID（`ioreg`） |
| Linux | `/etc/machine-id` |
| Windows | BIOS UUID（`wmic csproduct get UUID`） |
| 回退 | hostname + username |

安全性说明：
- 密钥绑定本机硬件 ID，换机器无法解密
- PBKDF2 10 万轮迭代，抗暴力破解
- Fernet 内置 HMAC-SHA256，防篡改
- 同一台机器上任何用户都能解密（没有额外口令保护）

使用 `python3 auto_login.py --show` 可以查看解密后的所有账号信息。
