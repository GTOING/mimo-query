#!/usr/bin/env python3
"""MiMo 平台 Cookie 登录助手 — 半自动抓取并保存 Cookie"""

import http.server
import json
import os
import sys
import threading
import webbrowser
import urllib.parse
import urllib.request
import urllib.error
import socket

from common import COOKIE_FIELDS, MIMO_ORIGIN, build_cookie, parse_cookie_string
LOGIN_URL = f"{MIMO_ORIGIN}/login"
DETAIL_API = f"{MIMO_ORIGIN}/api/v1/tokenPlan/detail"

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mimo-accounts.json")

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>MiMo Cookie 登录</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f5f5f5; color: #333; padding: 40px 20px; }
  .card { max-width: 560px; margin: 0 auto; background: #fff;
          border-radius: 12px; padding: 32px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
  h1 { font-size: 20px; margin-bottom: 8px; }
  .subtitle { color: #666; font-size: 14px; margin-bottom: 24px; }
  label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 6px; }
  textarea { width: 100%; height: 120px; padding: 10px; border: 1px solid #ddd;
             border-radius: 8px; font-family: monospace; font-size: 13px;
             resize: vertical; }
  textarea:focus { outline: none; border-color: #4a90d9; }
  input[type="text"] { width: 100%; padding: 10px; border: 1px solid #ddd;
                       border-radius: 8px; font-size: 14px; margin-bottom: 20px; }
  input[type="text"]:focus { outline: none; border-color: #4a90d9; }
  .field { margin-bottom: 16px; }
  button { width: 100%; padding: 12px; background: #4a90d9; color: #fff;
           border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
           cursor: pointer; margin-top: 8px; }
  button:hover { background: #3a7bc8; }
  button:disabled { background: #aaa; cursor: not-allowed; }
  .result { margin-top: 16px; padding: 12px; border-radius: 8px; font-size: 14px;
            display: none; }
  .result.ok { display: block; background: #e8f5e9; color: #2e7d32; }
  .result.err { display: block; background: #fbe9e7; color: #c62828; }
  .steps { background: #f8f9fa; border-radius: 8px; padding: 16px;
           margin-bottom: 20px; font-size: 13px; line-height: 1.8; }
  .steps ol { padding-left: 20px; }
  .steps code { background: #e8e8e8; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
  .link { color: #4a90d9; text-decoration: none; }
  .link:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="card">
  <h1>MiMo Cookie 登录</h1>
  <p class="subtitle">粘贴浏览器 Cookie，自动保存账号配置</p>

  <div class="steps">
    <ol>
      <li>浏览器已打开 <a class="link" href="__LOGIN_URL__" target="_blank">MiMo 登录页</a>，请先登录</li>
      <li>登录后按 <code>F12</code> 打开 DevTools</li>
      <li>切到 <code>Application</code> → <code>Cookies</code> → <code>platform.xiaomimimo.com</code></li>
      <li>右键表格 → <code>Select All</code>，再右键 → <code>Copy</code> → <code>Copy all cookies as string</code><br>
          或直接从 <code>Network</code> 标签里复制任意请求的 <code>Cookie</code> 请求头</li>
      <li>粘贴到下方</li>
    </ol>
  </div>

  <form id="form">
    <div class="field">
      <label for="cookie">Cookie 字符串</label>
      <textarea id="cookie" placeholder="api-platform_slh=xxx; api-platform_ph=xxx; api-platform_serviceToken=xxx; userId=xxx"></textarea>
    </div>
    <div class="field">
      <label for="label">账号名称（可选）</label>
      <input type="text" id="label" placeholder="如：主账号、备用账号" />
    </div>
    <button type="submit" id="btn">保存</button>
  </form>
  <div id="result" class="result"></div>
</div>

<script>
document.getElementById("form").addEventListener("submit", async function(e) {
  e.preventDefault();
  var btn = document.getElementById("btn");
  var result = document.getElementById("result");
  btn.disabled = true;
  btn.textContent = "验证中...";
  result.className = "result";
  result.style.display = "none";

  var payload = {
    cookie: document.getElementById("cookie").value.trim(),
    label: document.getElementById("label").value.trim()
  };

  try {
    var resp = await fetch("/submit", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    var data = await resp.json();
    if (data.ok) {
      result.className = "result ok";
      result.textContent = "✓ " + data.message;
    } else {
      result.className = "result err";
      result.textContent = "✗ " + data.message;
    }
  } catch(err) {
    result.className = "result err";
    result.textContent = "✗ 请求失败: " + err.message;
  }
  btn.disabled = false;
  btn.textContent = "保存";
});
</script>
</body>
</html>"""


def validate_cookie(cookie_str):
    """调用 API 验证 cookie 是否有效，返回 (ok, message, plan_name)"""
    req = urllib.request.Request(DETAIL_API, method="GET", headers={
        "Accept": "*/*",
        "Accept-Language": "zh",
        "X-Timezone": "Asia/Shanghai",
        "Cookie": cookie_str,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        return False, f"网络错误: {e.reason}", ""
    except Exception as e:
        return False, f"请求失败: {e}", ""

    if data.get("code") != 0:
        return False, data.get("message") or f"API 错误码 {data.get('code')}", ""

    plan_name = data.get("data", {}).get("planName", "未知套餐")
    return True, "验证成功", plan_name


def load_config():
    """读取现有配置文件"""
    if not os.path.isfile(CONFIG_PATH):
        return []
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw if isinstance(raw, list) else []


def save_config(accounts):
    """保存配置文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "MiMoLogin/1.0"

    def log_message(self, format, *args):
        pass  # 静默日志

    def do_GET(self):
        if self.path == "/":
            body = HTML_PAGE.replace("__LOGIN_URL__", LOGIN_URL).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/submit":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        raw_cookie = body.get("cookie", "").strip()
        label = body.get("label", "").strip()

        if not raw_cookie:
            self._respond(False, "请粘贴 Cookie 字符串")
            return

        # 解析并验证
        fields = parse_cookie_string(raw_cookie)
        found = [f for f in COOKIE_FIELDS if f in fields]
        missing = [f for f in COOKIE_FIELDS if f not in fields]

        if missing:
            self._respond(False, f"缺少字段: {', '.join(missing)}（找到: {', '.join(found)}）")
            return

        cookie_str = build_cookie(fields)
        ok, message, plan_name = validate_cookie(cookie_str)

        if not ok:
            self._respond(False, message)
            return

        # 保存
        if not label:
            label = plan_name or "MiMo 账号"

        accounts = load_config()

        # 检查重复 label（合并更新，保留 username/password/email 等字段）
        for i, acc in enumerate(accounts):
            if acc.get("label") == label:
                acc["cookie"] = cookie_str
                save_config(accounts)
                self._respond(True, f"已覆盖更新「{label}」（{plan_name}）→ {CONFIG_PATH}")
                return

        accounts.append({"label": label, "cookie": cookie_str})
        save_config(accounts)
        self._respond(True, f"已保存「{label}」（{plan_name}）→ {CONFIG_PATH}")

    def _respond(self, ok, message):
        data = json.dumps({"ok": ok, "message": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    print(f"本地服务已启动: {url}")
    print(f"正在打开浏览器...")
    print(f"按 Ctrl+C 退出\n")

    # 先打开 MiMo 登录页，再打开本地表单页
    webbrowser.open(LOGIN_URL)
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")
        server.server_close()


if __name__ == "__main__":
    main()
