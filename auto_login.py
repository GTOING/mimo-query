#!/usr/bin/env python3
"""MiMo 平台自动登录 — Selenium 自动填写密码 + 手动短信验证 + 自动抓取 Cookie"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from getpass import getpass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "mimo-accounts.json")

MIMO_ORIGIN = "https://platform.xiaomimimo.com"
MIMO_CONSOLE = f"{MIMO_ORIGIN}/console/balance"

COOKIE_FIELDS = [
    "api-platform_slh",
    "api-platform_ph",
    "api-platform_serviceToken",
    "userId",
]

# ── 加密 ──────────────────────────────────────────────────────────────────────

def get_machine_id():
    """获取机器唯一标识，支持 macOS / Linux / Windows"""
    import platform
    system = platform.system()

    if system == "Darwin":
        try:
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                text=True, stderr=subprocess.DEVNULL,
            )
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            if m:
                return m.group(1)
        except Exception:
            pass

    elif system == "Linux":
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                with open(path, "r") as f:
                    mid = f.read().strip()
                    if mid:
                        return mid
            except Exception:
                continue

    elif system == "Windows":
        try:
            out = subprocess.check_output(
                ["wmic", "csproduct", "get", "UUID"],
                text=True, stderr=subprocess.DEVNULL,
            )
            for line in out.strip().splitlines()[1:]:
                uuid = line.strip()
                if uuid and uuid != "UUID":
                    return uuid
        except Exception:
            pass

    # 回退：hostname + user
    import socket
    return f"{socket.gethostname()}-{os.getlogin()}"


def make_fernet():
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    mid = get_machine_id().encode()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"mimo-query-salt", iterations=100_000)
    key = base64.urlsafe_b64encode(kdf.derive(mid))
    return Fernet(key)


def encrypt_text(plain):
    return make_fernet().encrypt(plain.encode()).decode()


def decrypt_text(token):
    return make_fernet().decrypt(token.encode()).decode()


# ── 配置文件 ──────────────────────────────────────────────────────────────────

def load_config():
    if not os.path.isfile(CONFIG_PATH):
        return []
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw if isinstance(raw, list) else []


def save_config(accounts):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


def find_account(accounts, label):
    for i, acc in enumerate(accounts):
        if acc.get("label") == label:
            return i, acc
    return -1, None


# ── 添加账号 ──────────────────────────────────────────────────────────────────

def add_account():
    label = input("账号名称（如：主账号）: ").strip()
    if not label:
        print("错误：名称不能为空")
        return

    username = input("手机号/邮箱: ").strip()
    if not username:
        print("错误：用户名不能为空")
        return

    password = getpass("密码（输入不可见）: ")
    if not password:
        print("错误：密码不能为空")
        return

    print("\n邮箱 IMAP 配置（用于自动读取验证码，可跳过）")
    email_addr = input("邮箱地址（如 xxx@163.com，跳过直接回车）: ").strip()
    email_pass = ""
    email_imap = ""
    if email_addr:
        email_pass = getpass("邮箱授权码（非登录密码，在邮箱设置→IMAP中获取）: ")
        email_imap = input("IMAP 服务器（默认自动识别，直接回车）: ").strip()
        if not email_imap:
            if "163.com" in email_addr or "126.com" in email_addr:
                email_imap = "imap.163.com"
            elif "qq.com" in email_addr or "foxmail.com" in email_addr:
                email_imap = "imap.qq.com"
            elif "gmail.com" in email_addr:
                email_imap = "imap.gmail.com"
            elif "outlook" in email_addr or "hotmail" in email_addr:
                email_imap = "outlook.office365.com"
            else:
                email_imap = input("无法自动识别，请手动输入 IMAP 服务器地址: ").strip()

    accounts = load_config()
    idx, existing = find_account(accounts, label)

    entry = {
        "label": label,
        "username": encrypt_text(username),
        "password": encrypt_text(password),
    }
    if email_addr and email_pass:
        entry["email"] = encrypt_text(email_addr)
        entry["email_pass"] = encrypt_text(email_pass)
        entry["email_imap"] = email_imap

    # 保留已有 cookie
    if existing:
        for key in ("cookie", "email", "email_pass", "email_imap"):
            if key in existing and key not in entry:
                entry[key] = existing[key]
        accounts[idx] = entry
        print(f"已更新「{label}」")
    else:
        accounts.append(entry)
        print(f"已添加「{label}」")

    save_config(accounts)
    print(f"→ {CONFIG_PATH}")


# ── IMAP 验证码读取 ───────────────────────────────────────────────────────────

def fetch_email_code(email_addr, email_pass, email_imap, timeout=90):
    """通过 IMAP 读取小米验证码邮件，自动解码并提取验证码"""
    import imaplib
    import email
    import re
    from email.header import decode_header

    print(f"  连接邮箱 {email_imap}...")

    try:
        mail = imaplib.IMAP4_SSL(email_imap, 993)

        # 163 邮箱要求登录前发送 ID 命令
        if "163.com" in email_imap or "126.com" in email_imap:
            try:
                tag = mail._new_tag()
                mail.send(tag + b' ID ("name" "mimo-query" "contact" "<test@test.com>" "version" "1.0.0" "vendor" "test")\r\n')
                while True:
                    line = mail.file.readline()
                    if line.startswith(tag):
                        break
            except Exception as e:
                print(f"  ID 命令: {e}")

        typ, dat = mail.login(email_addr, email_pass)
        if typ != "OK":
            print(f"  登录失败: {dat}")
            return None
        print(f"  IMAP 登录成功")

        mail.select("INBOX")

        code = _search_in_folder(mail, timeout)
        if code:
            return code

        # 兜底：搜索垃圾箱
        for junk_name in ('"Junk"', '"[Gmail]/Spam"', '"垃圾邮件"', '"Spam"'):
            try:
                status, _ = mail.select(junk_name)
                if status == "OK":
                    print(f"  搜索垃圾箱: {junk_name}")
                    code = _search_in_folder(mail, min(timeout, 15))
                    if code:
                        return code
            except Exception:
                continue

        mail.logout()
        return None

    except Exception as e:
        print(f"  邮件读取失败: {e}")
        return None


def _search_in_folder(mail, timeout):
    """在当前选中的文件夹中搜索小米验证码邮件"""
    import re
    from email.header import decode_header

    start = time.time()
    checked = set()

    while time.time() - start < timeout:
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            time.sleep(3)
            continue

        mail_ids = messages[0].split()
        for msg_id in reversed(mail_ids[-20:]):
            if msg_id in checked:
                continue
            checked.add(msg_id)

            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue

            import email as email_lib
            msg = email_lib.message_from_bytes(msg_data[0][1])

            # 解码主题
            subject = msg.get("Subject", "")
            decoded_subject = ""
            for part, enc in decode_header(subject):
                if isinstance(part, bytes):
                    decoded_subject += part.decode(enc or "utf-8", errors="ignore")
                else:
                    decoded_subject += part

            # 发件人
            sender = msg.get("From", "")
            print(f"  检查: {decoded_subject[:50]}")

            # 只看小米邮件
            if "xiaomi" not in sender.lower():
                continue

            # 解码正文（处理 multipart / quoted-printable / base64 / html）
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype in ("text/plain", "text/html"):
                        payload = part.get_payload(decode=True)
                        if payload:
                            try:
                                body += payload.decode(
                                    part.get_content_charset() or "utf-8",
                                    errors="ignore"
                                )
                            except Exception:
                                body += payload.decode(errors="ignore")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body += payload.decode(errors="ignore")

            # 提取 6 位验证码（保持字符串，不转 int，保留前导 0）
            matches = re.findall(r'\b(\d{6})\b', body)
            if matches:
                code = matches[0]
                print(f"  获取验证码成功: {code}")
                mail.logout()
                return code

        time.sleep(3)

    return None


# ── Selenium 自动登录 ─────────────────────────────────────────────────────────

def build_mimo_login_url():
    """构建 MiMo 平台的完整小米账号登录 URL"""
    from urllib.parse import quote
    callback = f"{MIMO_ORIGIN}/sts?sign=M7gfywevl3CG5YTTcZDifhK6IK8=&followup={quote(MIMO_CONSOLE, safe='')}"
    qs = quote(f"?callback={callback}", safe="")
    return (
        "https://account.xiaomi.com/fe/service/login/password"
        f"?_group=DEFAULT&sid=api-platform&qs={qs}"
        f"&callback={quote(callback, safe='')}"
        f"&_locale=zh_CN"
    )


def auto_login_account(label, username, password, email_creds=None, timeout=120):
    """自动登录单个账号，返回 (ok, cookie_dict_or_error_msg)
    email_creds: dict with keys email, email_pass, email_imap (all decrypted) or None
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])

    # 优先使用系统 chromedriver，失败再用 webdriver-manager 在线下载
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)

    try:
        login_url = build_mimo_login_url()
        print(f"  打开登录页...")
        driver.get(login_url)

        # 等待页面加载
        wait = WebDriverWait(driver, 15)

        # 填写用户名
        print(f"  填写账号: {username[:3]}***")
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[name="account"]')))
        user_input.clear()
        user_input.send_keys(username)

        # 填写密码
        print(f"  填写密码...")
        pwd_input = driver.find_element(By.CSS_SELECTOR, 'input[name="password"]')
        pwd_input.clear()
        pwd_input.send_keys(password)

        # 勾选"已阅读并同意"
        checkbox = driver.find_element(By.CSS_SELECTOR, '.mi-accept-terms .ant-checkbox-input')
        if not checkbox.is_selected():
            checkbox.click()
            print(f"  已勾选用户协议")

        # 点击登录按钮
        print(f"  点击登录...")
        login_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        login_btn.click()

        # 等待页面跳转（可能跳到安全验证页或直接登录成功）
        time.sleep(3)

        # 检测是否进入安全验证页
        if "verify" in driver.current_url.lower() or "security" in driver.current_url.lower():
            page_text = driver.page_source

            # 检测是否是手机验证（非邮箱），无法自动化则跳过
            if "安全手机" in page_text or "verifyPhone" in page_text:
                driver.quit()
                return False, "需要手机验证码，无法自动处理，已跳过"

            print(f"  检测到安全验证页，自动点击发送邮件...")
            try:
                send_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
                send_btn.click()
                time.sleep(2)

                # 检测"验证码发送过多"等错误
                page_text = driver.page_source
                if "发送过多" in page_text or "明天再试" in page_text:
                    driver.quit()
                    return False, "验证码发送过多，请明天再试"
                if "频繁" in page_text:
                    driver.quit()
                    return False, "操作过于频繁，请稍后再试"

                print(f"  验证邮件已发送！")
            except Exception:
                pass

            # 尝试用 IMAP 自动获取验证码
            if email_creds and email_creds.get("email"):
                print(f"  等待验证邮件到达（15秒）...")
                time.sleep(15)
                print(f"  通过 IMAP 自动读取验证码...")
                code = fetch_email_code(
                    email_creds["email"],
                    email_creds["email_pass"],
                    email_creds["email_imap"],
                    timeout=60,
                )
                if code:
                    try:
                        # 找到验证码输入框并填入
                        code_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR,
                                'input[type="text"], input[type="number"], input[type="tel"], input.ant-input')))
                        code_input.clear()
                        code_input.send_keys(code)
                        print(f"  验证码已自动填入: {code}")
                        # 尝试自动提交
                        time.sleep(1)
                        try:
                            submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                            submit_btn.click()
                            print(f"  已自动提交验证码")
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"  自动填入失败: {e}，请手动输入")
                else:
                    print(f"  未获取到验证码，请手动输入")
            else:
                print(f"\n  ⏳ 请查看邮箱，在浏览器中输入验证码（{timeout}秒超时）")
                print(f"  提示: 运行 --add 配置邮箱 IMAP 可自动填写验证码\n")
        else:
            print(f"  登录中，等待跳转...")

        # 等待 URL 跳转回 platform.xiaomimimo.com
        start = time.time()
        while time.time() - start < timeout:
            current_url = driver.current_url
            if "platform.xiaomimimo.com" in current_url and "/login" not in current_url:
                # 登录成功
                break
            time.sleep(1)
        else:
            driver.quit()
            return False, "超时：未检测到登录成功"

        print(f"  登录成功！正在抓取 Cookie...")
        time.sleep(2)  # 等待 Cookie 全部设置完成

        # 抓取 Cookie
        selenium_cookies = driver.get_cookies()
        cookie_dict = {}
        for c in selenium_cookies:
            cookie_dict[c["name"]] = c["value"]

        # 提取目标字段
        result = {}
        for field in COOKIE_FIELDS:
            val = cookie_dict.get(field, "")
            if val:
                result[field] = val

        missing = [f for f in COOKIE_FIELDS if f not in result]
        if missing:
            driver.quit()
            return False, f"缺少字段: {', '.join(missing)}"

        cookie_str = "; ".join(f"{k}={v}" for k, v in result.items())
        driver.quit()
        return True, cookie_str

    except Exception as e:
        print(f"  异常: {e}")
        try:
            driver.quit()
        except Exception:
            pass
        return False, str(e)
    finally:
        pass


def refresh_account(account, timeout=120):
    """刷新单个账号的 Cookie"""
    label = account["label"]

    enc_user = account.get("username", "")
    enc_pass = account.get("password", "")
    if not enc_user or not enc_pass:
        print(f"[{label}] 跳过：未配置用户名/密码（用 --add 添加）")
        return False

    try:
        username = decrypt_text(enc_user)
        password = decrypt_text(enc_pass)
    except Exception as e:
        print(f"[{label}] 解密失败: {e}")
        return False

    # 解密邮箱凭据（如有）
    email_creds = None
    enc_email = account.get("email", "")
    if enc_email:
        try:
            email_creds = {
                "email": decrypt_text(enc_email),
                "email_pass": decrypt_text(account.get("email_pass", "")),
                "email_imap": account.get("email_imap", ""),
            }
        except Exception:
            pass

    print(f"[{label}] 自动登录...")
    ok, result = auto_login_account(label, username, password, email_creds, timeout)

    if ok:
        account["cookie"] = result
        print(f"[{label}] ✓ Cookie 已更新")
        return True
    else:
        print(f"[{label}] ✗ {result}")
        return False


def show_accounts():
    """显示所有账号信息（解密）"""
    accounts = load_config()
    if not accounts:
        print("没有账号，请先添加：python3 auto_login.py --add")
        return

    for i, acc in enumerate(accounts):
        label = acc.get("label", f"账号 {i + 1}")
        print(f"{'─' * 40}")
        print(f"账号: {label}")

        # 解密凭据
        for field, display in [("username", "用户名"), ("password", "密码")]:
            enc = acc.get(field, "")
            if enc:
                try:
                    print(f"{display}: {decrypt_text(enc)}")
                except Exception:
                    print(f"{display}: (解密失败)")

        enc_email = acc.get("email", "")
        if enc_email:
            try:
                print(f"邮箱: {decrypt_text(enc_email)}")
            except Exception:
                print(f"邮箱: (解密失败)")

        enc_email_pass = acc.get("email_pass", "")
        if enc_email_pass:
            try:
                print(f"邮箱授权码: {decrypt_text(enc_email_pass)}")
            except Exception:
                print(f"邮箱授权码: (解密失败)")

        email_imap = acc.get("email_imap", "")
        if email_imap:
            print(f"IMAP: {email_imap}")

        # Cookie 状态
        cookie = acc.get("cookie", "")
        if cookie:
            print(f"Cookie: ✓ 已有（{len(cookie)} 字符）")
        else:
            has_creds = acc.get("username") and acc.get("password")
            print(f"Cookie: ✗ 未获取" + ("，运行 auto_login.py 可自动刷新" if has_creds else ""))

    print(f"{'─' * 40}")


def check_cookies(accounts):
    """检查所有账号的 Cookie 有效性，返回 (valid, invalid) 列表"""
    valid = []
    invalid = []
    for acc in accounts:
        label = acc.get("label", "")
        cookie = acc.get("cookie", "")
        if not cookie:
            invalid.append((label, "无 Cookie"))
            continue
        try:
            from urllib.request import Request, urlopen
            from urllib.error import URLError
            req = Request(
                "https://platform.xiaomimimo.com/api/v1/tokenPlan/detail",
                headers={"Accept": "*/*", "X-Timezone": "Asia/Shanghai", "Cookie": cookie},
            )
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            if data.get("code") == 0:
                plan = data.get("data", {}).get("planName", "未知")
                valid.append((label, plan))
            else:
                invalid.append((label, f"API 错误: {data.get('message', data.get('code'))}"))
        except URLError as e:
            if "401" in str(e):
                invalid.append((label, "Cookie 已过期"))
            else:
                invalid.append((label, f"网络错误: {e.reason}"))
        except Exception as e:
            invalid.append((label, str(e)))
    return valid, invalid


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MiMo 平台自动登录工具")
    parser.add_argument("--add", action="store_true", help="添加/更新账号（交互式输入用户名密码）")
    parser.add_argument("--show", action="store_true", help="显示所有账号信息（解密）")
    parser.add_argument("--check", action="store_true", help="检查所有账号 Cookie 有效性")
    parser.add_argument("-a", "--account", metavar="LABEL",
                        help="指定账号（逗号分隔支持多个，如 -a \"A,B\"）")
    parser.add_argument("--all", action="store_true", help="强制刷新所有账号（忽略 Cookie 有效性）")
    parser.add_argument("--timeout", type=int, default=120, help="短信验证等待超时秒数（默认 120）")
    args = parser.parse_args()

    if args.add:
        add_account()
        return

    if args.show:
        show_accounts()
        return

    accounts = load_config()
    if not accounts:
        print("没有账号，请先添加：python3 auto_login.py --add")
        sys.exit(1)

    if args.check:
        valid, invalid = check_cookies(accounts)
        print(f"\n✓ 有效（{len(valid)} 个）:")
        for label, plan in valid:
            print(f"  {label} — {plan}")
        if invalid:
            print(f"\n✗ 无效（{len(invalid)} 个）:")
            for label, reason in invalid:
                print(f"  {label} — {reason}")
        else:
            print("\n所有账号 Cookie 有效，无需刷新")
        return

    if args.account:
        labels = [l.strip() for l in args.account.split(",")]
        targets = []
        for l in labels:
            idx, acc = find_account(accounts, l)
            if not acc:
                all_labels = ", ".join(a["label"] for a in accounts)
                print(f"未找到「{l}」，可用账号: {all_labels}")
                sys.exit(1)
            targets.append(acc)
    elif args.all:
        targets = accounts
    else:
        # 默认：只刷新 Cookie 无效的账号
        valid, invalid = check_cookies(accounts)
        if not invalid:
            print("所有账号 Cookie 有效，无需刷新")
            return
        print(f"发现 {len(invalid)} 个账号需要刷新:")
        for label, reason in invalid:
            print(f"  ✗ {label} — {reason}")
        print()
        invalid_labels = {label for label, _ in invalid}
        targets = [a for a in accounts if a["label"] in invalid_labels]

    success = 0
    for acc in targets:
        if refresh_account(acc, args.timeout):
            success += 1

    # 保存更新后的配置
    save_config(accounts)
    print(f"\n完成：{success}/{len(targets)} 个账号更新成功")


if __name__ == "__main__":
    main()
