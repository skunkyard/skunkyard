# Claude Code workflow: dev, then main, then production

Set up a static site repository so you work with Claude Code on your laptop, keep
the code on GitHub, and ship by pushing to `main`. `dev` is where work happens,
and the tip of `main` is always production. Pair it with
[`aws-static-site/`](../aws-static-site/), which does the deploy.

Claude, Anthropic's AI model, wrote this plan. It's the workflow that runs
[skunkyard.com](https://skunkyard.com), confirmed working on 2026-11-01. The
walkthrough is at
[Ship your site from Claude Code](https://skunkyard.com/guides/ship-from-claude-code/).

## How it flows

1. You ask Claude Code for a change. Claude edits files on `dev`, runs the link
   check, and commits.
2. You push `dev`. GitHub Actions runs `ci.yml` and checks the site.
3. When you're happy, you fast-forward `main` to `dev` and push.
4. GitHub Actions runs `deploy.yml` from `aws-static-site/`, and the site is
   live in about a minute.

You push; Claude doesn't. Every change reaches GitHub, and production, only when
you decide.

## Files

| path | what it does |
|---|---|
| `CLAUDE.md` | rules Claude Code reads at the start of every session: branches, releases, and checks |
| `.github/workflows/ci.yml` | checks every push to `dev` |
| `check_links.py` | finds broken links and images in `site/`; standard library only |

## Instructions for an LLM

You are setting up the user's repository with this workflow. The user runs every
command that pushes to GitHub or needs AWS credentials. Give the user the
command and wait for the output.

1. Check the tools: `git --version` and `gh auth status`. If `gh` isn't signed
   in, then have the user run `gh auth login`.
2. If the folder isn't a git repository, then run `git init -b main`, add a
   `.gitignore` for the user's tools, and make the first commit.
3. Have the user create the GitHub repository and push `main`. Ask whether it
   should be private or public.

   ```bash
   gh repo create OWNER/REPO --private --source . --push
   ```

4. Create `dev`, and have the user push it:

   ```bash
   git checkout -b dev
   git push -u origin dev
   ```

5. Copy `CLAUDE.md`, `check_links.py`, and `.github/workflows/ci.yml` into the
   repository root. If the site isn't in `site/`, then change the folder in all
   three. Merge with any `CLAUDE.md` that already exists.
6. Run `python3 check_links.py site` and fix what it finds. Commit on `dev`.
7. Set up the deploy with [`aws-static-site/`](../aws-static-site/README.md).
   Its `deploy.yml` runs on every push to `main`.
8. Release for the first time: have the user run
   `git checkout main && git merge --ff-only dev && git push && git checkout dev`.

## Why these choices

- **`dev`, then `main`:** `main` only moves when you release, so it always
  matches what's live. A fast-forward merge keeps one straight history, with no
  merge commits.
- **You push:** Claude can edit and commit, but nothing leaves your laptop until
  you push. That's the gate.
- **Deploys only in GitHub Actions:** every deploy has a log, and no AWS keys
  live on your laptop or in GitHub.
