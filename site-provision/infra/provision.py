#!/usr/bin/env python3
"""Provision a static site with mail, end to end, for any project. Safe to rerun.

Steps, each skipped when already done:
  1. CloudFormation stack from infra/site.yaml (Route 53 zone, certificate, S3, CloudFront, mail DNS, deploy role).
  2. Porkbun: point the domain's name servers at the Route 53 zone.
  3. GitHub: set the repository variables the deploy workflow reads, then run the deploy.
  4. Purelymail: add the domain, turn off account reset, and create each mailbox.

Usage:
  python3 infra/provision.py --profile <aws-profile> --domain example.com --repo owner/name --mailbox hello

Credentials come from these environment variables, or a hidden prompt when one is unset, so any
secrets manager can supply them (for example `op run --env-file=.env -- python3 infra/provision.py ...`):
  PORKBUN_API_KEY, PORKBUN_SECRET_API_KEY   Porkbun > Account > API Access; also turn on API access for the domain.
  PURELYMAIL_API_TOKEN                      Purelymail > Account > API.
Each new mailbox asks for its first password; press Enter to have one generated and shown once. The script
stores no password.
AWS uses --profile (single sign-on; run `aws sso login --profile <profile>` first). GitHub uses the gh CLI login.
"""
import argparse
import functools
import getpass
import json
import os
import pathlib
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

TEMPLATE = pathlib.Path(__file__).with_name("site.yaml")
PORKBUN = "https://api.porkbun.com/api/json/v3"
PURELYMAIL = "https://purelymail.com/api/v0"


def log(msg):
    print(f"• {msg}", flush=True)


def run(*cmd, capture=True):
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode:
        sys.exit(f"Command failed: {' '.join(cmd[:4])}...\n{result.stderr.strip()}")
    return result.stdout.strip() if capture else ""


@functools.lru_cache(maxsize=None)
def secret(name):
    """The user's secrets manager fills the variable (op run, CI, .env); otherwise ask without echo."""
    return os.environ.get(name) or getpass.getpass(f"{name}: ") or sys.exit(f"{name} is empty.")


def first_password(address):
    """The user's own first password, or a generated one when they press Enter. Returns (password, generated)."""
    typed = getpass.getpass(f"Password for {address} (Enter to generate one): ")
    return (typed, False) if typed else (secrets.token_urlsafe(24), True)


def post_json(url, body, headers=None):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except ValueError:
            raise RuntimeError(f"{url}: HTTP {e.code}") from e


def porkbun(path, keys, **body):
    data = post_json(f"{PORKBUN}{path}", {"apikey": keys[0], "secretapikey": keys[1], **body})
    if data.get("status") != "SUCCESS":
        raise RuntimeError(f"Porkbun {path}: {data.get('code', '')} {data.get('message', data)}")
    return data


def purelymail(endpoint, token, **body):
    data = post_json(f"{PURELYMAIL}/{endpoint}", body, {"Purelymail-Api-Token": token})
    if "result" not in data:
        raise RuntimeError(f"Purelymail {endpoint}: {data.get('code', '')} {data.get('message', data)}")
    return data["result"]


def normalize_ns(names):
    return sorted(n.lower().rstrip(".") for n in names)


def oidc_subject(repo):
    """The repo part of GitHub's OIDC subject; repos on immutable subjects use owner@id/name@id."""
    sub = json.loads(run("gh", "api", f"repos/{repo}/actions/oidc/customization/sub"))
    return sub["sub_claim_prefix"].removeprefix("repo:") if sub.get("use_immutable_subject") else repo


def default_stack(domain):
    return domain.replace(".", "-") + "-site"


class Aws:
    def __init__(self, profile, region):
        self.base = ["aws", "--profile", profile, "--region", region, "--output", "json"]

    def __call__(self, *args):
        out = run(*self.base, *args)
        return json.loads(out) if out else {}

    def stack(self, name):
        result = subprocess.run([*self.base, "cloudformation", "describe-stacks", "--stack-name", name], capture_output=True, text=True)
        return json.loads(result.stdout)["Stacks"][0] if result.returncode == 0 else None


def provision_stack(aws, args, params):
    stack = aws.stack(args.stack)
    if stack is None:
        log(f"Creating stack {args.stack}")
        aws("cloudformation", "create-stack", "--stack-name", args.stack, "--template-body", f"file://{TEMPLATE}",
            "--capabilities", "CAPABILITY_IAM", "--parameters",
            *[f"ParameterKey={k},ParameterValue={v}" for k, v in params.items()])
    elif stack["StackStatus"].endswith("_COMPLETE") and "ROLLBACK" not in stack["StackStatus"]:
        log(f"Updating stack {args.stack} if the template changed")
        run(*aws.base, "cloudformation", "deploy", "--stack-name", args.stack, "--template-file", str(TEMPLATE),
            "--capabilities", "CAPABILITY_IAM", "--no-fail-on-empty-changeset", "--parameter-overrides",
            *[f"{k}={v}" for k, v in params.items()], capture=False)
    elif not stack["StackStatus"].endswith("_IN_PROGRESS"):
        sys.exit(f"Stack {args.stack} is {stack['StackStatus']}. Fix or delete it in the CloudFormation console, then rerun.")

    # The certificate can't validate until the registrar delegates to the zone, so read the zone first.
    for _ in range(60):
        resources = aws("cloudformation", "describe-stack-resources", "--stack-name", args.stack, "--logical-resource-id", "HostedZone")
        zone = resources["StackResources"][0] if resources.get("StackResources") else None
        if zone and zone["ResourceStatus"].endswith("_COMPLETE"):
            return aws("route53", "get-hosted-zone", "--id", zone["PhysicalResourceId"])["DelegationSet"]["NameServers"]
        time.sleep(10)
    sys.exit("The hosted zone did not appear within 10 minutes. Check the stack events.")


def wait_for_stack(aws, name):
    log("Waiting for the stack to finish (the certificate validates once the name servers propagate)")
    for _ in range(180):
        status = aws.stack(name)["StackStatus"]
        if status.endswith("_COMPLETE") and "ROLLBACK" not in status:
            return {o["OutputKey"]: o["OutputValue"] for o in aws.stack(name).get("Outputs", [])}
        if "FAILED" in status or "ROLLBACK" in status:
            sys.exit(f"Stack {name} is {status}. Check the stack events.")
        time.sleep(20)
    sys.exit("The stack did not finish within an hour. Rerun this script to keep waiting.")


def provision_registrar(domain, nameservers):
    keys = (secret("PORKBUN_API_KEY"), secret("PORKBUN_SECRET_API_KEY"))
    current = porkbun(f"/domain/getNs/{domain}", keys).get("ns", [])
    if normalize_ns(current) == normalize_ns(nameservers):
        log("Porkbun already uses the Route 53 name servers")
        return
    log(f"Setting Porkbun name servers to {', '.join(nameservers)}")
    porkbun(f"/domain/updateNs/{domain}", keys, ns=nameservers)


def provision_github(repo, outputs):
    for var, key in (("AWS_ROLE_ARN", "DeployRoleArn"), ("S3_BUCKET", "BucketName"), ("CLOUDFRONT_DISTRIBUTION_ID", "DistributionId")):
        run("gh", "variable", "set", var, "--repo", repo, "--body", outputs[key])
    log("Set GitHub variables; starting the deploy workflow")
    run("gh", "workflow", "run", "deploy.yml", "--repo", repo)


def provision_mail(domain, mailboxes):
    token = secret("PURELYMAIL_API_TOKEN")
    domains = [d["name"] for d in purelymail("listDomains", token)["domains"]]
    if domain not in domains:
        log(f"Adding {domain} to Purelymail (retries while DNS propagates)")
        for attempt in range(30):
            try:
                purelymail("addDomain", token, domainName=domain)
                break
            except RuntimeError as e:
                if attempt == 29:
                    raise
                log(f"Not yet: {e}. Retrying in 60 seconds.")
                time.sleep(60)
    # Anyone who controls the domain's DNS could otherwise reset the Purelymail admin password.
    purelymail("updateDomainSettings", token, name=domain, allowAccountReset=False, recheckDns=True)

    users = set(purelymail("listUser", token)["users"])
    # A mailbox's password is typed or shown on screen, never written to a log or a file.
    if {f"{b}@{domain}" for b in mailboxes} - users and not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.exit("Creating a mailbox asks for its first password; run this step from a terminal.")
    for box in mailboxes:
        address = f"{box}@{domain}"
        if address in users:
            log(f"Mailbox {address} exists")
            continue
        password, generated = first_password(address)
        purelymail("createUser", token, userName=box, domainName=domain, password=password,
                   enablePasswordReset=False, sendWelcomeEmail=False)
        log(f"Created {address}")
        if generated:
            # Purelymail can't force a change at first sign-in, so this message has to.
            log(f"First password, shown once: {password}\n  Sign in at https://inbox.purelymail.com now, change it under "
                "Settings, and save the new one where you keep passwords. This script keeps no copy.")
        log(f"Read its mail at https://inbox.purelymail.com; manage it from your Purelymail admin account at https://purelymail.com")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--domain", required=True)
    p.add_argument("--repo", required=True, help="owner/name of the GitHub repository that deploys the site")
    p.add_argument("--mailbox", action="append", default=[], help="local part of a mailbox to create; repeatable")
    p.add_argument("--stack", help="CloudFormation stack name (default: domain with dashes, plus -site)")
    p.add_argument("--profile", default=os.environ.get("AWS_PROFILE"), help="AWS profile (default: $AWS_PROFILE)")
    p.add_argument("--region", default="us-east-1", help="must be us-east-1 for CloudFront certificates")
    p.add_argument("--create-oidc-provider", action="store_true", help="only for an AWS account without the GitHub OIDC provider")
    p.add_argument("--skip-mail", action="store_true")
    args = p.parse_args()
    args.stack = args.stack or default_stack(args.domain)
    if not args.profile:
        p.error("set --profile or AWS_PROFILE")

    aws = Aws(args.profile, args.region)
    aws("sts", "get-caller-identity")  # fails fast when the sign-in expired
    params = {"DomainName": args.domain, "GitHubRepo": oidc_subject(args.repo),
              "CreateOidcProvider": str(args.create_oidc_provider).lower(),
              "PurelymailOwnership": "" if args.skip_mail else purelymail("getOwnershipCode", secret("PURELYMAIL_API_TOKEN"))["code"]}

    nameservers = provision_stack(aws, args, params)
    provision_registrar(args.domain, nameservers)
    outputs = wait_for_stack(aws, args.stack)
    provision_github(args.repo, outputs)
    if not args.skip_mail:
        provision_mail(args.domain, args.mailbox)
    log(f"Done: https://{args.domain}")


if __name__ == "__main__":
    main()
