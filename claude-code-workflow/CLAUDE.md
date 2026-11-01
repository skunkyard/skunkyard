# Claude instructions

This repository is a static website. Its files are in `site/`.

## Branches and releases

- Work happens on `dev`. Never commit to `main` directly.
- The tip of `main` is production. A push to `main` deploys through GitHub
  Actions (`.github/workflows/deploy.yml`).
- Commit when asked. The user pushes; don't run `git push`.
- To release, the user merges `dev` into `main` with a fast-forward and pushes:
  `git checkout main && git merge --ff-only dev && git push && git checkout dev`.
- Never deploy from this machine: no `pulumi up`, `aws s3 sync`, or CloudFront
  invalidations. Every deploy runs in GitHub Actions so it has a log.

## Before each commit

- Run `python3 check_links.py site`. It must report 0 broken links.
- Every page in `site/` needs a title and a description, and `site/404.html`
  must exist.

## AWS

- The user runs every command that needs AWS credentials. Give the user the
  command and wait for the output.
