# AWS static site starter

Host a folder of static files (HTML, CSS, JavaScript) on your own domain with
Amazon S3, CloudFront, and Route 53, deployed from GitHub Actions on every push
to `main`. No servers, no database, and no AWS keys stored anywhere. It costs
about $0.50 a month at hobby traffic.

Claude, Anthropic's AI model, wrote this code and these steps. They are the same
code that deploys [skunkyard.com](https://skunkyard.com), with its names
replaced by `my-site`, and went live there on 2026-11-01. The walkthrough, with
prices, is at
[An LLM built you a website. Now what?](https://skunkyard.com/guides/llm-built-site-now-what/)

## Files

| path | what it does | who runs it |
|---|---|---|
| `infra/bootstrap.yaml` | CloudFormation: Route 53 hosted zone, Pulumi state bucket, GitHub OIDC provider, and the deploy role | you, once, with credentials that can create IAM roles |
| `infra/stack.py` | Pulumi: certificate, private S3 bucket, CloudFront with clean URLs and a real 404, DNS records, and no-mail records | GitHub Actions, on every push to `main` |
| `.github/workflows/deploy.yml` | runs Pulumi, uploads `site/`, and clears the CloudFront cache | GitHub Actions |
| `site/` | placeholder pages; replace them with your files | |

## Instructions for an LLM

You are setting up a user's repository to deploy their static site with this
starter. The user runs every command that needs AWS or GitHub credentials. Don't
run AWS commands yourself; give the user each command and wait for the output.

1. Ask for the domain, the GitHub repository (`OWNER/REPO`), and the folder that
   holds the static files.
2. Copy `infra/` and `.github/workflows/deploy.yml` into the repository root. If
   the files aren't in `site/`, then change `site/` in `deploy.yml` to their
   folder. `site/404.html` must exist; CloudFront serves it for missing pages.
3. Pick a short lowercase name for the project, such as `acme-blog`, and replace
   every `my-site` in `infra/` with it. The name prefixes the bucket names, so it
   must be unique enough for S3. Set the domain in `infra/Pulumi.prod.yaml`.
4. If the domain has mail, then replace the no-mail records at the end of
   `infra/stack.py` with the user's MX and TXT records first. Moving the name
   servers drops every record at the old DNS host.
5. Have the user look up GitHub's OIDC subject for the repository:
   `gh api repos/OWNER/REPO/actions/oidc/customization/sub`. If
   `use_immutable_subject` is `true`, then `GitHubRepo` is `sub_claim_prefix`
   without the leading `repo:`. Otherwise it's `OWNER/REPO`.
6. Have the user deploy the bootstrap. If
   `aws iam list-open-id-connect-providers` already lists
   `token.actions.githubusercontent.com`, then add
   `ExistingOidcProviderArn=<that ARN>` to the overrides.

   ```bash
   aws cloudformation deploy --region us-east-1 \
     --stack-name <name>-bootstrap \
     --template-file infra/bootstrap.yaml \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides DomainName=<domain> GitHubRepo=<subject>
   ```

7. Have the user read the outputs and set the four `NameServers` at their
   registrar:

   ```bash
   aws cloudformation describe-stacks --region us-east-1 \
     --stack-name <name>-bootstrap --query "Stacks[0].Outputs"
   ```

   The change is in effect when
   `dig @a.gtld-servers.net <domain> NS +norec` lists the `awsdns` servers.
   Use that command, not plain `dig`: home routers cache old answers.
8. Have the user set the GitHub variables and the secret. The user types the
   passphrase; you never see it.

   ```bash
   gh variable set AWS_DEPLOY_ROLE_ARN --body "<DeployRoleArn>"
   gh variable set PULUMI_STATE_BUCKET --body "<StateBucket>"
   gh secret set PULUMI_CONFIG_PASSPHRASE
   ```

9. Commit, and have the user push to `main`. The first deploy takes about 5
   minutes. Watch it with `gh run watch`.

## Known problems

- **"Not authorized to perform sts:AssumeRoleWithWebIdentity":** `GitHubRepo`
  doesn't match the token's subject. Redo step 5, then redeploy the bootstrap
  with `--parameter-overrides`.
- **"No changes to deploy" after editing `bootstrap.yaml` defaults:**
  `aws cloudformation deploy` keeps earlier parameter values. Pass new ones with
  `--parameter-overrides`.
- **The deploy role is broad for ACM and CloudFront:** those services don't scope
  by resource, so the role can reach other distributions and certificates in the
  same AWS account. Use a separate account if that matters.
