# MiMo Query — 定时任务配置参考

## 概述

通过 Hermes cron 系统定时执行 MiMo 套餐查询，采用智能刷新机制：先检测问题，仅对过期账号刷新。

## 推荐配置

### 智能每日查询（推荐）

每天早上 9 点自动检测 + 刷新过期账号 + 查询，结果推送到 Telegram：

```bash
hermes cron create \
  --name "mimo-daily-query" \
  --schedule "0 9 * * *" \
  --prompt "执行 MiMo 套餐查询智能工作流：
1. 运行 mimo-query.py 检测所有账号状态
2. 解析输出，识别需要刷新的账号（Cookie 过期或无 Cookie）
3. 仅对需要刷新的账号运行 auto_login.py -a "账号1,账号2"
4. 再次运行 mimo-query.py 获取最终结果
5. 格式化输出：各账号套餐详情 + 刷新结果摘要" \
  --deliver "telegram" \
  --toolsets "terminal"
```

### 仅查询（不刷新）

如果 Cookie 刚刷新过，可以跳过自动登录：

```bash
hermes cron create \
  --name "mimo-query-only" \
  --schedule "0 9 * * *" \
  --prompt "运行 MiMo 套餐查询：执行 mimo-query.py 查询所有账号套餐用量，格式化输出结果。" \
  --deliver "telegram" \
  --toolsets "terminal"
```

### 每周完整刷新 + 查询

每周一早上 9 点强制刷新所有账号：

```bash
hermes cron create \
  --name "mimo-weekly-refresh" \
  --schedule "0 9 * * 1" \
  --prompt "执行 MiMo 完整刷新工作流：
1. 运行 auto_login.py --all 强制刷新所有账号 Cookie
2. 运行 mimo-query.py 查询所有账号套餐用量
3. 格式化输出结果" \
  --deliver "telegram" \
  --toolsets "terminal"
```

## 管理命令

```bash
# 查看所有定时任务
hermes cron list

# 手动触发一次
hermes cron run mimo-daily-query

# 暂停任务
hermes cron pause mimo-daily-query

# 恢复任务
hermes cron resume mimo-daily-query

# 删除任务
hermes cron remove mimo-daily-query
```

## 输出格式示例

### 智能刷新流程输出

```
🔍 检测账号状态...

✓ 主账号 (gtoingx-163) — 已有有效 Cookie
✓ 备用账号 (xqh1667399679) — 已有有效 Cookie
✗ 测试账号 (geminixqh2) — Cookie 未获取
✗ 旧账号 (191qq) — Cookie 已过期

📝 需要刷新: 2 个账号 (geminixqh2, 191qq)

🔄 刷新 Cookie...
[geminixqh2] 自动登录...
  ✓ Cookie 已更新
[191qq] 自动登录...
  ✗ 需要手机验证码，无法自动处理

📊 最终查询结果:

🔵 主账号 (gtoingx-163)
  套餐: Pro
  额度: 700,000,000 Credits
  已用: 21,293,523 (3.0%)
  有效期至: 2026-06-19 23:59:59

🟢 备用账号 (xqh1667399679)
  套餐: Free
  额度: 1,000,000 Credits
  已用: 500,000 (50.0%)
  有效期至: 2026-06-19 23:59:59

🟡 测试账号 (geminixqh2)
  套餐: Free
  额度: 1,000,000 Credits
  已用: 0 (0.0%)
  有效期至: 2026-06-19 23:59:59

⚠️ 跳过的账号:
  - 191qq: 需要手机验证码，无法自动处理
```

## 注意事项

1. **PYTHONHOME 冲突**：cron 任务运行时也需要清除 PYTHONHOME，terminal tool 会自动处理
2. **浏览器依赖**：auto_login.py 需要 Chrome 浏览器，确保系统已安装
3. **IMAP 依赖**：自动读取验证码需要邮箱 IMAP 配置正确
4. **频率限制**：小米平台对验证码发送有频率限制，不要过于频繁地刷新
5. **推送目标**：`--deliver "telegram"` 推送到 Telegram，`--deliver "all"` 推送到所有平台
6. **智能跳过**：脚本会自动跳过无法处理的错误（手机验证/频繁操作），不会阻塞整个流程
