#!/usr/bin/env python3
"""Write an iPhone or Mac configuration profile (.mobileconfig) for a Purelymail mailbox.

Installing the profile sets every server field at once, including the outgoing sign-in
that iOS labels optional but Purelymail requires. The profile holds no password; the
phone asks for it once during install and uses it for both servers.

Usage:
  python3 infra/mail_profile.py hello@example.com --name "Example" --out ~/Desktop
Then AirDrop the file to the phone and install it from Settings > Profile Downloaded.
"""
import argparse
import pathlib
import plistlib
import uuid


def profile(address, name):
    domain = address.split("@", 1)[1]
    ident = ".".join(reversed(domain.split("."))) + ".mail"
    account = {
        "PayloadType": "com.apple.mail.managed",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"{ident}.{address.split('@')[0]}",
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": address,
        "EmailAccountDescription": name,
        "EmailAccountName": name,
        "EmailAccountType": "EmailTypeIMAP",
        "EmailAddress": address,
        "IncomingMailServerHostName": "imap.purelymail.com",
        "IncomingMailServerPortNumber": 993,
        "IncomingMailServerUseSSL": True,
        "IncomingMailServerAuthentication": "EmailAuthPassword",
        "IncomingMailServerUsername": address,
        "OutgoingMailServerHostName": "smtp.purelymail.com",
        "OutgoingMailServerPortNumber": 465,
        "OutgoingMailServerUseSSL": True,
        "OutgoingMailServerAuthentication": "EmailAuthPassword",
        "OutgoingMailServerUsername": address,
        "OutgoingPasswordSameAsIncomingPassword": True,
    }
    return {
        "PayloadContent": [account],
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": ident,
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": f"{name} mail",
        "PayloadRemovalDisallowed": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("address")
    p.add_argument("--name", help="account name shown in Mail (default: the domain)")
    p.add_argument("--out", default=".", help="folder to write the profile to")
    args = p.parse_args()
    name = args.name or args.address.split("@", 1)[1]
    path = pathlib.Path(args.out).expanduser() / f"{args.address.replace('@', '-at-')}.mobileconfig"
    path.write_bytes(plistlib.dumps(profile(args.address, name)))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
