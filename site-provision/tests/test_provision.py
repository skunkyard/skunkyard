import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "infra"))
import provision  # noqa: E402


def response(body):
    return mock.MagicMock(__enter__=lambda s: io.BytesIO(json.dumps(body).encode()), __exit__=lambda *a: False)


class ProvisionTest(unittest.TestCase):
    def test_normalize_ns_ignores_case_order_and_trailing_dot(self):
        self.assertEqual(provision.normalize_ns(["NS-2.awsdns.org.", "ns-1.awsdns.com"]),
                         provision.normalize_ns(["ns-1.awsdns.com.", "ns-2.awsdns.org"]))

    def test_default_stack(self):
        self.assertEqual(provision.default_stack("example.com"), "example-com-site")

    def test_porkbun_error_raises(self):
        with mock.patch("urllib.request.urlopen", return_value=response({"status": "ERROR", "message": "API access disabled"})):
            with self.assertRaisesRegex(RuntimeError, "API access disabled"):
                provision.porkbun("/domain/getNs/x.com", ("k", "s"))

    def test_purelymail_returns_result_and_raises_on_error(self):
        with mock.patch("urllib.request.urlopen", return_value=response({"type": "success", "result": {"users": []}})):
            self.assertEqual(provision.purelymail("listUser", "t"), {"users": []})
        with mock.patch("urllib.request.urlopen", return_value=response({"type": "error", "code": "dnsCheck", "message": "Ownership record not found"})):
            with self.assertRaisesRegex(RuntimeError, "Ownership record not found"):
                provision.purelymail("addDomain", "t", domainName="x.com")

    def test_secret_prefers_the_environment_then_prompts(self):
        provision.secret.cache_clear()
        with mock.patch.dict("os.environ", {"PURELYMAIL_API_TOKEN": "from-env"}), mock.patch("getpass.getpass") as ask:
            self.assertEqual(provision.secret("PURELYMAIL_API_TOKEN"), "from-env")
            ask.assert_not_called()
        provision.secret.cache_clear()
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch("getpass.getpass", return_value="typed"):
            self.assertEqual(provision.secret("PURELYMAIL_API_TOKEN"), "typed")
        provision.secret.cache_clear()

    def test_first_password_uses_typed_or_generates(self):
        with mock.patch("getpass.getpass", return_value="mine"):
            self.assertEqual(provision.first_password("a@x.com"), ("mine", False))
        with mock.patch("getpass.getpass", return_value=""):
            password, generated = provision.first_password("a@x.com")
        self.assertTrue(generated)
        self.assertEqual(len(password), 32)

    def test_stack_params_leave_out_what_a_rerun_wasnt_given(self):
        args = mock.Mock(domain="x.com", create_oidc_provider=False, csp=None, google_site_verification=None)
        self.assertEqual(provision.stack_params(args, "o/r", None), {"DomainName": "x.com", "GitHubRepo": "o/r"})
        args = mock.Mock(domain="x.com", create_oidc_provider=True, csp="default-src 'self'",
                         google_site_verification=["google-site-verification=abc", "google-site-verification=def"])
        self.assertEqual(provision.stack_params(args, "o/r", "proof=1"),
                         {"DomainName": "x.com", "GitHubRepo": "o/r", "CreateOidcProvider": "true",
                          "PurelymailOwnership": "proof=1", "ContentSecurityPolicy": "default-src 'self'",
                          "GoogleSiteVerification": "google-site-verification=abc",
                          "GoogleSiteVerification2": "google-site-verification=def"})

    def test_registrar_removes_porkbun_defaults_and_adds_mail_before_moving_name_servers(self):
        calls = []
        def fake(path, keys, **body):
            calls.append((path, body))
            if path.startswith("/domain/getNs"):
                return {"ns": ["curitiba.porkbun.com"]}
            if path.startswith("/dns/retrieve"):
                return {"records": [{"id": "1", "content": "pixie.porkbun.com"}, {"id": "2", "content": "fwd1.porkbun.com"},
                                    {"id": "3", "content": "my-own.example.net"}, {"id": "4", "content": "proof=1"},
                                    {"id": "5", "type": "NS", "content": "curitiba.ns.porkbun.com"}]}
            return {}
        with mock.patch.object(provision, "porkbun", side_effect=fake), mock.patch.object(provision, "secret", return_value="k"):
            provision.provision_registrar("x.com", ["ns-1.awsdns.com"], "proof=1")
        paths = [p for p, _ in calls]
        self.assertIn("/dns/delete/x.com/1", paths)
        self.assertIn("/dns/delete/x.com/2", paths)
        self.assertNotIn("/dns/delete/x.com/3", paths)
        self.assertIn("/dns/delete/x.com/4", paths)
        self.assertNotIn("/dns/delete/x.com/5", paths)
        mx = [b for p, b in calls if p == "/dns/create/x.com" and b["type"] == "MX"]
        self.assertEqual(mx[0]["prio"], "50")
        self.assertTrue(all("prio" not in b for p, b in calls if p == "/dns/create/x.com" and b["type"] != "MX"))
        self.assertEqual(paths.count("/dns/create/x.com"), 7)
        self.assertEqual(paths[-1], "/domain/updateNs/x.com")

    def test_wait_for_stack_accepts_a_rolled_back_update_and_stops_on_failure(self):
        aws = mock.Mock()
        aws.stack.return_value = {"StackStatus": "UPDATE_ROLLBACK_COMPLETE", "Outputs": [{"OutputKey": "A", "OutputValue": "1"}]}
        self.assertEqual(provision.wait_for_stack(aws, "s"), {"A": "1"})
        aws.stack.return_value = {"StackStatus": "UPDATE_ROLLBACK_FAILED"}
        with self.assertRaises(SystemExit):
            provision.wait_for_stack(aws, "s")


if __name__ == "__main__":
    unittest.main()
