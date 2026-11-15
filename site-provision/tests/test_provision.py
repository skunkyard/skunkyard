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


if __name__ == "__main__":
    unittest.main()
