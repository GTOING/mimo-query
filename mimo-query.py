#!/usr/bin/env python3
"""查询 Xiaomi MiMo 平台套餐信息（支持多账号）"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from common import COOKIE_FIELDS, MIMO_ORIGIN, build_cookie

ENDPOINTS = {
    "detail": "/api/v1/tokenPlan/detail",
    "usage": "/api/v1/tokenPlan/usage",
}

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mimo-accounts.json")


class MimoQueryError(RuntimeError):
    """Base error with a stable type for machine parsing."""
    error_type = "api_error"


class CookieExpiredError(MimoQueryError):
    error_type = "unauthorized"


class NetworkError(MimoQueryError):
    error_type = "network_error"


class ApiError(MimoQueryError):
    error_type = "api_error"


def classify_error(exc):
    return getattr(exc, "error_type", "unknown_error")


def request_api(path, cookie):
    url = f"{MIMO_ORIGIN}{path}"
    req = urllib.request.Request(url, method="GET", headers={
        "Accept": "*/*",
        "Accept-Language": "zh",
        "X-Timezone": "Asia/Shanghai",
        "Cookie": cookie,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise CookieExpiredError(f"HTTP {e.code}: Cookie 已过期或无权限") from e
        raise NetworkError(f"HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise NetworkError(f"网络错误: {e.reason}") from e
    except TimeoutError as e:
        raise NetworkError("网络超时") from e
    if data.get("code") != 0:
        message = data.get("message") or f"API error code {data.get('code')}"
        if str(data.get("code")) in {"401", "403"} or "unauthorized" in message.lower():
            raise CookieExpiredError(message)
        raise ApiError(message)
    return data.get("data")


def build_cookie_from_args(args):
    """从 key=value 参数构建 cookie 字符串"""
    pairs = {}
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            pairs[k.strip()] = v.strip()

    known = {f for f in COOKIE_FIELDS if f in pairs}
    if known:
        return build_cookie(pairs)

    return args[0] if args else ""


def build_cookie_from_env():
    """从环境变量构建 cookie"""
    pairs = {}
    for field in COOKIE_FIELDS:
        val = os.environ.get(field, "").strip()
        if val:
            pairs[field] = val
    if pairs:
        return build_cookie(pairs)
    return os.environ.get("MIMO_COOKIE", "").strip()


def parse_usage_items(items):
    result = {}
    for item in items or []:
        name = item.get("name", "")
        if name:
            result[name] = {
                "used": item.get("used", 0),
                "limit": item.get("limit", 0),
                "percent": item.get("percent", 0),
            }
    return result


def fetch_subscription(cookie):
    detail = request_api(ENDPOINTS["detail"], cookie)
    usage = request_api(ENDPOINTS["usage"], cookie)

    usage_items = parse_usage_items(usage.get("usage", {}).get("items"))
    plan_token = usage_items.get("plan_total_token", {})

    return {
        "plan_code": detail.get("planCode", ""),
        "plan_name": detail.get("planName", ""),
        "current_period_end": detail.get("currentPeriodEnd", ""),
        "expired": detail.get("expired", False),
        "enable_auto_renew": detail.get("enableAutoRenew", False),
        "auto_renew_discount": detail.get("autoRenewDiscount", ""),
        "total_credits": plan_token.get("limit", 0),
        "used_credits": plan_token.get("used", 0),
        "usage_percent": plan_token.get("percent", 0),
        "month_usage_percent": usage.get("usage", {}).get("percent", 0),
    }


def save_history(accounts_data):
    """将查询结果追加到历史文件"""
    history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mimo-history.json")
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

    history.append(accounts_data)
    history = history[-50:]  # 只保留最近 50 条

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"历史记录已保存（共 {len(history)} 条）", file=sys.stderr)


def format_number(n):
    return f"{n:,}"


def print_info(info, label=None):
    used_pct = info["usage_percent"] * 100
    print(f"查询时间   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if label:
        print(f"账号       {label}")
    print(f"套餐       {info['plan_name']}")
    print(f"额度       {format_number(info['total_credits'])} Credits")
    print(f"已用       {format_number(info['used_credits'])}（{used_pct:.1f}%）")
    print(f"有效期至   {info['current_period_end']}")
    print(f"自动续费   {'开启' if info['enable_auto_renew'] else '关闭'}")
    if info["expired"]:
        print("状态       已过期")


def load_accounts(config_path):
    """从 JSON 配置文件加载账号列表，返回 [(label, cookie, skip_reason), ...]"""
    path = config_path or DEFAULT_CONFIG
    if not os.path.isfile(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError(f"配置文件格式错误：顶层应为数组，实际为 {type(raw).__name__}")

    accounts = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"账号 #{i + 1} 格式错误：应为对象")
        label = entry.get("label", "").strip() or f"账号 {i + 1}"
        cookie = entry.get("cookie", "").strip()
        if not cookie:
            has_creds = entry.get("username") and entry.get("password")
            reason = "Cookie 未获取，请运行 auto_login.py" if has_creds else "未配置 Cookie"
            accounts.append((label, "", reason))
        else:
            accounts.append((label, cookie, None))

    return accounts


def query_single(cookie):
    """查询单个账号，返回 info dict"""
    return fetch_subscription(cookie)


def query_accounts(accounts, save_history_flag=False, output_json=False, dry_run=False):
    """并发查询多账号，按原始顺序输出结果。"""
    skipped = []  # (index, label, reason)
    futures = {}  # future -> (index, label)

    with ThreadPoolExecutor(max_workers=5) as pool:
        for i, (label, cookie, reason) in enumerate(accounts):
            if reason:
                skipped.append((i, label, reason))
            else:
                futures[pool.submit(query_single, cookie)] = (i, label)

    results = {}  # index -> (label, info_or_exception)
    for future in futures:
        i, label = futures[future]
        try:
            results[i] = (label, future.result())
        except Exception as e:
            results[i] = (label, e)

    is_multi = len(accounts) > 1
    errors = 0
    queried = 0
    first = True

    all_items = sorted(
        [(i, label, reason, None) for i, label, reason in skipped] +
        [(i, label, None, res) for i, (label, res) in results.items()]
    )

    history_data = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "accounts": {}}

    for i, label, reason, res in all_items:
        if reason:
            errors += 1
            history_data["accounts"][label] = {"status": "skipped", "reason": reason}
            continue
        queried += 1
        if isinstance(res, Exception):
            errors += 1
            history_data["accounts"][label] = {
                "status": "error",
                "error_type": classify_error(res),
                "reason": str(res),
            }
        else:
            history_data["accounts"][label] = {
                "status": "ok",
                "plan": res.get("plan_name", ""),
                "quota": res.get("total_credits", 0),
                "used": res.get("used_credits", 0),
                "usage_percent": res.get("usage_percent", 0),
                "expires": res.get("current_period_end", ""),
                "auto_renew": res.get("enable_auto_renew", False),
            }

    if output_json:
        print(json.dumps(history_data, ensure_ascii=False, indent=2))
    else:
        for i, label, reason, res in all_items:
            if is_multi:
                if not first:
                    print()
                first = False
                print(f"=== {label} ===")
            if reason:
                print(f"跳过: {reason}")
            elif isinstance(res, Exception):
                print(f"错误: {res}", file=sys.stderr)
            else:
                print_info(res, label=None if is_multi else label)

    if save_history_flag and history_data["accounts"] and not dry_run:
        save_history(history_data)

    return queried, errors


def main():
    parser = argparse.ArgumentParser(
        description="查询 Xiaomi MiMo 平台套餐信息",
        usage="%(prog)s [--all | --account LABEL] [--config PATH]\n"
              "       %(prog)s [cookie_string | key=value ...]",
    )
    parser.add_argument("cookie_args", nargs="*", metavar="COOKIE",
                        help="cookie 字符串或 key=value 参数（单账号模式）")
    parser.add_argument("--all", action="store_true",
                        help="查询配置文件中所有账号")
    parser.add_argument("--account", "-a", metavar="LABEL",
                        help="查询配置文件中指定 label 的账号")
    parser.add_argument("--config", "-c", metavar="PATH",
                        help=f"配置文件路径（默认 {DEFAULT_CONFIG}）")
    parser.add_argument("--save-history", action="store_true",
                        help="查询后自动保存结果到 mimo-history.json")
    parser.add_argument("--json", action="store_true",
                        help="以 JSON 格式输出，便于脚本解析")
    parser.add_argument("--dry-run", action="store_true",
                        help="演练模式：执行查询但不写入历史文件")

    args = parser.parse_args()

    # 模式 1：命令行直接传 cookie（原有行为，向后兼容）
    if args.cookie_args:
        cookie = build_cookie_from_args(args.cookie_args)
        try:
            info = query_single(cookie)
            print_info(info)
        except Exception as e:
            print(f"错误: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # 尝试加载配置文件
    try:
        accounts = load_accounts(args.config)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"配置文件错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 模式 2：配置文件多账号查询
    if accounts and (args.all or args.account):
        if args.all:
            targets = accounts
        else:
            targets = [(l, c, r) for l, c, r in accounts if l == args.account]
            if not targets:
                labels = ", ".join(l for l, _, _ in accounts)
                print(f"未找到账号 '{args.account}'，可用账号: {labels}", file=sys.stderr)
                sys.exit(1)

        queried, _ = query_accounts(
            targets,
            save_history_flag=args.save_history,
            output_json=args.json,
            dry_run=args.dry_run,
        )
        if queried == 0:
            sys.exit(1)
        return

    # 模式 3：有配置文件但没指定 --all/--account，也默认查全部
    if accounts:
        queried, _ = query_accounts(
            accounts,
            save_history_flag=args.save_history,
            output_json=args.json,
            dry_run=args.dry_run,
        )
        if queried == 0:
            sys.exit(1)
        return

    # 模式 4：无参数无配置文件，尝试环境变量
    cookie = build_cookie_from_env()
    if cookie:
        try:
            info = query_single(cookie)
            print_info(info)
        except Exception as e:
            print(f"错误: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # 无任何凭据
    parser.print_usage()
    print(f"""
用法:
  python3 {sys.argv[0]} <cookie字符串>
  python3 {sys.argv[0]} key1=value1 key2=value2 ...
  MIMO_COOKIE="..." python3 {sys.argv[0]}
  python3 {sys.argv[0]} --all
  python3 {sys.argv[0]} --account <label>

配置文件 ({DEFAULT_CONFIG}):
  [
    {{
      "label": "主账号",
      "cookie": "api-platform_slh=xxx; api-platform_ph=xxx; api-platform_serviceToken=xxx; userId=xxx"
    }},
    {{
      "label": "备用账号",
      "cookie": "..."
    }}
  ]

Cookie 字段（4 个）:
  api-platform_slh, api-platform_ph, api-platform_serviceToken, userId

获取方法:
  1. 浏览器登录 platform.xiaomimimo.com
  2. F12 → Application → Cookies → platform.xiaomimimo.com
  3. 复制上述 4 个字段的值""")
    sys.exit(1)


if __name__ == "__main__":
    main()
