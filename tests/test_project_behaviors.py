import contextlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommonBehaviorTests(unittest.TestCase):
    def test_common_parse_cookie_string_supports_standard_and_tab_formats(self):
        import common

        standard = "api-platform_slh=a; api-platform_ph=b; api-platform_serviceToken=c; userId=d; other=x"
        self.assertEqual(
            common.parse_cookie_string(standard),
            {
                "api-platform_slh": "a",
                "api-platform_ph": "b",
                "api-platform_serviceToken": "c",
                "userId": "d",
            },
        )

        tab = "api-platform_slh\ta\napi-platform_ph\tb\napi-platform_serviceToken\tc\nuserId\td\n"
        self.assertEqual(common.parse_cookie_string(tab)["userId"], "d")

    def test_common_mask_secret_keeps_short_safe_preview(self):
        import common

        self.assertEqual(common.mask_secret(""), "")
        self.assertEqual(common.mask_secret("13800138000"), "138****8000")
        self.assertEqual(common.mask_email("someone@example.com"), "s***e@example.com")


class AutoLoginSafetyTests(unittest.TestCase):
    def setUp(self):
        self.auto_login = load_module("auto_login.py", "auto_login_under_test")

    def test_show_accounts_masks_secrets_by_default(self):
        account = {
            "label": "main",
            "username": "enc-user",
            "password": "enc-pass",
            "email": "enc-email",
            "email_pass": "enc-email-pass",
            "email_imap": "imap.example.com",
            "cookie": "abc123",
        }
        decrypted = {
            "enc-user": "13800138000",
            "enc-pass": "real-password",
            "enc-email": "someone@example.com",
            "enc-email-pass": "mail-auth-code",
        }
        with mock.patch.object(self.auto_login, "load_config", return_value=[account]), \
             mock.patch.object(self.auto_login, "decrypt_text", side_effect=lambda token: decrypted[token]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.auto_login.show_accounts()

        text = out.getvalue()
        self.assertIn("138****8000", text)
        self.assertIn("s***e@example.com", text)
        self.assertNotIn("real-password", text)
        self.assertNotIn("mail-auth-code", text)

    def test_show_accounts_can_reveal_secrets_explicitly(self):
        account = {"label": "main", "username": "u", "password": "p", "cookie": "abc"}
        with mock.patch.object(self.auto_login, "load_config", return_value=[account]), \
             mock.patch.object(self.auto_login, "decrypt_text", side_effect=lambda token: {"u": "user", "p": "pass"}[token]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.auto_login.show_accounts(show_secrets=True)
        self.assertIn("密码: pass", out.getvalue())


class MimoQueryBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.mimo_query = load_module("mimo-query.py", "mimo_query_under_test")

    def test_success_history_entries_include_status_ok(self):
        accounts = [("main", "cookie", None)]
        with mock.patch.object(self.mimo_query, "query_single", return_value={
            "plan_name": "Pro",
            "total_credits": 700,
            "used_credits": 7,
            "usage_percent": 0.01,
            "current_period_end": "2026-06-01 00:00:00",
            "enable_auto_renew": False,
            "expired": False,
        }), mock.patch.object(self.mimo_query, "save_history") as save_history:
            self.mimo_query.query_accounts(accounts, save_history_flag=True)

        history = save_history.call_args.args[0]
        self.assertEqual(history["accounts"]["main"]["status"], "ok")

    def test_json_output_is_machine_readable(self):
        accounts = [("main", "cookie", None)]
        with mock.patch.object(self.mimo_query, "query_single", return_value={
            "plan_name": "Pro",
            "total_credits": 700,
            "used_credits": 7,
            "usage_percent": 0.01,
            "current_period_end": "2026-06-01 00:00:00",
            "enable_auto_renew": False,
            "expired": False,
        }):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.mimo_query.query_accounts(accounts, output_json=True)
        data = json.loads(out.getvalue())
        self.assertEqual(data["accounts"]["main"]["status"], "ok")
        self.assertEqual(data["accounts"]["main"]["plan"], "Pro")

    def test_dry_run_skips_history_write(self):
        accounts = [("main", "", "Cookie 未获取，请运行 auto_login.py")]
        with mock.patch.object(self.mimo_query, "save_history") as save_history:
            self.mimo_query.query_accounts(accounts, save_history_flag=True, dry_run=True)
        save_history.assert_not_called()


if __name__ == "__main__":
    unittest.main()
