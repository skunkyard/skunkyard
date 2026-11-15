# Site provision

One command takes a domain from "just registered" to a live static site with
working mail: AWS hosting, registrar name servers, GitHub deploy variables, and
mailboxes. It drives each service through its API, so there is no clicking
through dashboards. It checks the current state before each step and skips what
is already done, so you can rerun it after a failure or a template change.

It uses CloudFormation only, with no Pulumi and no state bucket. For the
Pulumi-based setup that deploys skunkyard.com, see
[`aws-static-site/`](../aws-static-site/).

| service | what the script does |
|---|---|
| AWS | creates or updates the CloudFormation stack in `infra/site.yaml`: Route 53 zone, certificate, private S3 bucket, CloudFront with a www-to-apex redirect, mail DNS records, and a deploy role |
| Porkbun | points the domain's name servers at the Route 53 zone |
| GitHub | sets the repository variables the deploy workflow reads, then runs the deploy |
| Purelymail | adds the domain, turns off account reset for it, and creates each mailbox with a generated first password saved in the macOS Keychain; see [Mail](#mail) |

GitHub Actions holds no AWS keys. It signs in through GitHub's OIDC provider and
assumes a role that AWS trusts only for `main` of your repository. The role can
only write to the site's bucket and clear the site's CloudFront cache. The
script reads the repository's OIDC subject from GitHub, so it works for
repositories on GitHub's immutable subject format too.

## Files

| path | what it does | who runs it |
|---|---|---|
| `infra/provision.py` | the provisioning script; Python 3.9+ standard library only | you |
| `infra/site.yaml` | the CloudFormation template | `provision.py` |
| `.github/workflows/deploy.yml` | on every push to `main`, uploads `site/` and clears the cache | GitHub Actions |
| `tests/test_provision.py` | unit tests: `python3 -m unittest discover tests` | you |

## Requirements

- A Mac (credentials come from the macOS Keychain), with the AWS CLI and the
  GitHub CLI (`gh`) signed in.
- AWS credentials that can create IAM roles and CloudFormation stacks.
- A domain at Porkbun and a Purelymail account. To skip mail, pass `--skip-mail`;
  the stack then leaves out the mail records.

## Instructions for an LLM

You are setting up a user's repository to host their static site with this kit.
The user runs every command that needs credentials, unless they tell you to run
it.

1. Ask for the domain, the GitHub repository (`OWNER/REPO`), the folder that
   holds the static files, the AWS profile, and the mailboxes to create.
2. Copy `infra/` and `.github/workflows/deploy.yml` into the repository root. If
   the files aren't in `site/`, then change `site/` in `deploy.yml`. If the site
   needs a build, then add the build step where the workflow's comment says.
   Commit and push.
3. If the domain already has records at Porkbun that must keep working, then list
   them for the user first. Moving the name servers drops every record at the old
   DNS host.
4. Have the user save the API credentials once. Each command prompts for the
   value:

   ```sh
   security add-generic-password -a "$USER" -s porkbun-api-key -w
   security add-generic-password -a "$USER" -s porkbun-secret-api-key -w
   security add-generic-password -a "$USER" -s purelymail-api-token -w
   ```

   The Porkbun keys come from **Account > API Access**. API access must also be
   turned on for the domain. The Purelymail token comes from **Account > API**.

5. Have the user sign in to AWS, then run:

   ```sh
   python3 infra/provision.py --profile <aws-profile> --domain <domain> --repo <OWNER/REPO> --mailbox <name>
   ```

   Add `--create-oidc-provider` only if
   `aws iam list-open-id-connect-providers` doesn't list
   `token.actions.githubusercontent.com`. The stack waits on the certificate
   until the new name servers propagate, usually 5 to 30 minutes.

6. Write the project's own command into the project's README. Keep `infra/`
   free of project details, so it stays reusable.

## Mail

Each mailbox lives on Purelymail.

- **Webmail:** https://inbox.purelymail.com. Sign in with the full email address and the mailbox password.
- **Admin:** https://purelymail.com, with your Purelymail admin account. Reset mailbox passwords, add mailboxes, and set routing rules there.

### First sign-in

The provisioning script gives each new mailbox a generated password and saves it in the Keychain item `purelymail-<address>`. To read it, run `security find-generic-password -s purelymail-hello@example.com -w`.

1. Sign in to webmail with that password.
2. Change the password under **Settings**, and save the new one in your password manager.
3. Delete the Keychain copy, which no longer works: `security delete-generic-password -s purelymail-hello@example.com`.

### Mail on an iPhone

Checked on 2026-11-15 against [Apple's guide](https://support.apple.com/en-us/102619), [Purelymail's phone page](https://purelymail.com/docs/setup/phone), and [Purelymail's server settings](https://purelymail.com/docs/setup/technical).

1. Open **Settings**, tap **Apps**, tap **Mail**, tap **Mail Accounts**, then tap **Add Account**.
2. Enter `hello@example.com`, then tap **Next**.
3. Tap **Add Other Account**, then tap **Mail Account**.
4. Enter your name, `hello@example.com`, the mailbox password, and a description. Type the password by hand; don't accept an AutoFill suggestion. Tap **Next**.
5. If iOS shows **IMAP** and **POP** choices, tap **IMAP**, then fill in both sections and tap **Next**:

   | | Incoming Mail Server | Outgoing Mail Server |
   |---|---|---|
   | Host Name | `imap.purelymail.com` | `smtp.purelymail.com` |
   | User Name | `hello@example.com` | `hello@example.com` |
   | Password | the mailbox password | the same password |

   Purelymail: "username and password for the outgoing mail server are NOT optional." iOS labels them optional; fill them in.

6. Tap **Save**.
7. Check the outgoing sign-in, even if iOS set the account up on its own: open **Settings > Apps > Mail > Mail Accounts**, the account, **Account**, **SMTP**, then `smtp.purelymail.com`. **User Name** must be `hello@example.com`, **Password** filled in, **Use SSL** on, **Server Port** `465`. Tap **Done** and stay on the screen until **Verifying** finishes, which can take several minutes, longer on cellular. Leaving early can keep the settings from saving, and mail then sits in the Outbox. On 2026-11-15, waiting it out sent the stuck message.
8. Send a test message to another address and reply to it.

If iOS asks to set up the account without SSL, tap **No**. Purelymail needs encryption on both servers: IMAP port 993, SMTP port 465 (Purelymail also lists 587 with STARTTLS). If two-factor authentication is on for the mailbox, use a Purelymail app password instead of the mailbox password.
