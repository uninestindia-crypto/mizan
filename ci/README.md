# CI workflow, staged outside `.github/` on purpose

`gates-workflow.yml` is the repository gate workflow. It is **not** at
`.github/workflows/ci.yml`, where it needs to be to run, and this file explains why so nobody
assumes it was a mistake.

## Why it is parked here

Pushing any file under `.github/workflows/` requires a token with the `workflow` OAuth scope. The
token authenticated in this environment carries `gist`, `read:org`, `repo` — no `workflow` — so the
push is rejected:

```
! [remote rejected] main -> main (refusing to allow an OAuth App to create or update
                                 workflow `.github/workflows/ci.yml` without `workflow` scope)
```

This already cost the file once. It was committed at `38d8c81d`, could not be pushed, and the commit
was then dropped from `main` — a reasonable move by whoever was trying to get their own work past
the same rejection, but it removed the file from the tree entirely. Parking the content at a path
that pushes normally means the next person to hit that rejection does not silently delete it again.

## Activating it

Two steps, in this order. The first is the founder's — it needs a browser.

```bash
gh auth refresh -s workflow
```

```bash
mkdir -p .github/workflows
git mv ci/gates-workflow.yml .github/workflows/ci.yml
git rm ci/README.md
git commit -m "ci: activate the repository gate workflow"
git push origin main
```

## What it runs, and why on Windows

Every step is a command this repository already runs by hand, at the same strictness: `uv sync
--frozen`, `ruff check`, `ruff format --check`, strict `mypy src launcher.py scripts`, pytest in
normal **and reverse file order**, both craft-checker self-tests, and both audits.

Reverse order is not padding. A suite green forwards and red backwards is not green, and this
repository pins a shared fixed `--basetemp=tmp/pytest`, which makes cross-test coupling plausible
enough to test for.

It runs on `windows-latest` because the release artifact is a PyInstaller Windows x64 bundle. A
Linux runner would be cheaper and would not represent what ships.

## What this does not do

Running is not blocking. Making these gates **required** before merge needs branch protection or a
ruleset, and both return `403 Upgrade to GitHub Pro or make this repository public` on a private
repository under a free User plan. That is a plan decision, not a configuration one, and it is
recorded in `agent_context/work/active/20260825-claude-program-majors.md` under Major #1.
