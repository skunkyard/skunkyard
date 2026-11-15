import plistlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "infra"))
import mail_profile  # noqa: E402


class MailProfileTest(unittest.TestCase):
    def test_outgoing_server_signs_in_with_the_incoming_password(self):
        data = plistlib.loads(plistlib.dumps(mail_profile.profile("hello@example.com", "Example")))
        account = data["PayloadContent"][0]
        self.assertEqual(account["OutgoingMailServerUsername"], "hello@example.com")
        self.assertTrue(account["OutgoingPasswordSameAsIncomingPassword"])
        self.assertEqual(account["OutgoingMailServerAuthentication"], "EmailAuthPassword")
        self.assertEqual((account["OutgoingMailServerPortNumber"], account["OutgoingMailServerUseSSL"]), (465, True))
        self.assertEqual(account["PayloadIdentifier"], "com.example.mail.hello")


if __name__ == "__main__":
    unittest.main()
