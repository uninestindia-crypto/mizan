#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lrk.py -- Launch Readiness Kit.

The evidence machine. It does not decide whether your software is good; it
makes it impossible to CLAIM your software is good without proof a human can
open, read, and check the hash of.

Zero third-party dependencies. Python 3.8+. Windows / macOS / Linux.

Quick start
-----------
    python lrk.py init --name "My App" --profile web,api,db,auth
    python lrk.py run G1.03 -- npm run typecheck
    python lrk.py manual G0.09 --status pass --note "Money paths: signup, checkout, refund"
    python lrk.py attach G8.13 ./friction-log.md --caption "Customer Zero session"
    python lrk.py status
    python lrk.py report
    python lrk.py certify
    python lrk.py bundle

Design rules that are deliberately hard to cheat
------------------------------------------------
1. `run` is the only way to produce EXECUTED proof. It records the command,
   the working directory, both output streams, the exit code, the duration,
   the host, and the git commit -- then hashes the log.
2. A check whose mode is `cmd` can never reach the strongest proof level by
   assertion. It will be printed in the report as ASSERTED and the
   certificate will refuse to say GO.
3. Every evidence file is hashed into MANIFEST.sha256. `verify` re-hashes and
   reports any file that changed after the fact.
4. `certify` computes the verdict from the data. It has no opinion and cannot
   be persuaded.
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from catalog import CATALOG, GATES, SEVERITIES, TAGS, gate_of  # type: ignore
except Exception as exc:  # pragma: no cover
    sys.stderr.write(
        "FATAL: cannot import catalog.py -- it must sit next to lrk.py.\n%s\n" % exc
    )
    raise SystemExit(2)

SCHEMA = 1
DIRNAME = ".launch"

# Windows consoles default to a legacy codepage (cp1252). Most modern test
# runners and linters emit Unicode, so echoing their output would raise
# UnicodeEncodeError and lose the whole run. Never let a console encoding
# limitation destroy captured evidence.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass
STATUS_ORDER = ["fail", "todo", "asserted", "waived", "na", "pass"]
PROOF_RANK = {"none": 0, "asserted": 1, "attached": 2, "executed": 3}

# Console colour, disabled when piped or on a dumb terminal.
_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(code, text):
    if not _COLOR:
        return text
    return "\033[%sm%s\033[0m" % (code, text)


def green(t):
    return c("32", t)


def red(t):
    return c("31;1", t)


def yellow(t):
    return c("33", t)


def dim(t):
    return c("2", t)


def bold(t):
    return c("1", t)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def today():
    return _dt.date.today().isoformat()


def slugify(text, maxlen=48):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text or "").strip("-").lower()
    return (s[:maxlen] or "item").strip("-")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.0f %s" % (n, unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%d B" % n


def git(root, *args):
    try:
        r = subprocess.run(["git"] + list(args), cwd=root, capture_output=True, timeout=20)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", "replace").strip()
    except Exception:
        pass
    return ""


def die(msg, code=2):
    sys.stderr.write(red("ERROR: ") + msg + "\n")
    raise SystemExit(code)


# Tokens the caller means as shell syntax, not as literal text. Everything else
# that contains shell-special characters gets re-quoted, because the calling
# shell already stripped the user's quotes before we saw argv.
_SHELL_OPERATORS = {"&&", "||", "|", ";", "&", ">", ">>", "<", "<<", "2>", "2>&1", "(", ")"}
_NEEDS_QUOTING = re.compile(r"""[\s"'`$&|;<>(){}\[\]*?!#~^%]""")


def resolve_shell(preference="auto"):
    """Decide which shell interprets the command. Returns (executable, name).

    On Windows `auto` prefers Git Bash when it is available. Every command in this
    kit's documentation is POSIX -- pipes, single quotes, $VAR, backslash-escaped
    regexes -- and cmd.exe mangles all of it. Routing through bash makes the kit
    behave identically on every platform. `--shell cmd` is the escape hatch.
    """
    if preference == "cmd":
        return (os.environ.get("COMSPEC", "cmd.exe") if os.name == "nt" else None,
                "cmd" if os.name == "nt" else "sh")
    if preference == "bash":
        exe = shutil.which("bash")
        if not exe:
            die("--shell bash requested but bash is not on PATH.")
        return exe, "bash"
    if os.name == "nt":
        exe = shutil.which("bash")
        if exe:
            return exe, "bash"
        return os.environ.get("COMSPEC", "cmd.exe"), "cmd"
    return None, "sh"


def rejoin(argv, shell_name="sh"):
    """Rebuild a shell command line from argv without losing the caller's quoting.

    `lrk run G1.07 -- git grep -nE "a|b(c)"` arrives as argv where the pattern is
    a single element whose quotes the calling shell already consumed. Joining on
    spaces would hand `a|b(c)` to the shell as syntax. So: re-quote anything that
    needs it, except genuine shell operators, which the caller means as operators.
    """
    if len(argv) == 1:
        # One element means the caller wrote a whole shell line and quoted it
        # themselves. Pass it through untouched.
        return argv[0]
    out = []
    for a in argv:
        if a in _SHELL_OPERATORS or not a:
            out.append(a)
        elif _NEEDS_QUOTING.search(a):
            if shell_name == "cmd":
                out.append('"%s"' % a.replace('"', '""'))
            else:
                out.append("'%s'" % a.replace("'", "'\\''"))
        else:
            out.append(a)
    return " ".join(out)


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------

class Kit:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.dir = os.path.join(self.root, DIRNAME)
        self.state_path = os.path.join(self.dir, "state.json")
        self.evidence_dir = os.path.join(self.dir, "evidence")
        self.attach_dir = os.path.join(self.dir, "attachments")
        self.report_dir = os.path.join(self.dir, "report")
        self.state = None

    # -- lifecycle ---------------------------------------------------------
    def exists(self):
        return os.path.isfile(self.state_path)

    def load(self):
        if not self.exists():
            die("no .launch found under %s -- run `lrk.py init` first." % self.root)
        with open(self.state_path, "r", encoding="utf-8") as fh:
            self.state = json.load(fh)
        if self.state.get("schema") != SCHEMA:
            die("state.json schema %r is not supported by this lrk.py (expects %d)."
                % (self.state.get("schema"), SCHEMA))
        return self.state

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.state, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.state_path)

    def audit(self, action, detail):
        self.state.setdefault("log", []).append(
            {"at": now_iso(), "action": action, "detail": detail}
        )

    # -- results -----------------------------------------------------------
    def result(self, cid):
        return self.state.setdefault("results", {}).setdefault(
            cid, {"status": "todo", "proof": "none", "records": [], "updated": None}
        )

    def profile(self):
        return set(self.state["project"].get("profile") or [])

    def applicable(self, tags):
        if "always" in tags:
            return True
        return bool(set(tags) & self.profile())

    def applicable_checks(self):
        out = []
        for cid, title, sev, tags, mode in CATALOG:
            if self.applicable(tags):
                out.append((cid, title, sev, tags, mode))
        return out

    def recompute_proof(self, cid):
        r = self.result(cid)
        best = "none"
        for rec in r["records"]:
            kind = rec.get("kind")
            if kind == "cmd":
                best = "executed"
            elif kind == "attach" and PROOF_RANK[best] < PROOF_RANK["attached"]:
                best = "attached"
            elif kind == "note" and PROOF_RANK[best] < PROOF_RANK["asserted"]:
                best = "asserted"
        r["proof"] = best
        return best


def find_root(explicit=None):
    if explicit:
        return os.path.abspath(explicit)
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, DIRNAME)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(os.getcwd())
        cur = parent


# --------------------------------------------------------------------------
# stack detection
# --------------------------------------------------------------------------

DETECTORS = [
    # (marker file/dir, label, suggested commands as dict)
    ("package.json", "Node.js / JavaScript", {
        "install": "npm ci", "build": "npm run build", "test": "npm test",
        "lint": "npm run lint", "typecheck": "npx tsc --noEmit",
        "audit": "npm audit --audit-level=high", "start": "npm start"}),
    ("pnpm-lock.yaml", "pnpm workspace", {"install": "pnpm install --frozen-lockfile"}),
    ("yarn.lock", "Yarn", {"install": "yarn install --immutable"}),
    ("bun.lockb", "Bun", {"install": "bun install --frozen-lockfile", "test": "bun test"}),
    ("tsconfig.json", "TypeScript", {"typecheck": "npx tsc --noEmit"}),
    ("next.config.js", "Next.js", {"build": "npx next build"}),
    ("next.config.mjs", "Next.js", {"build": "npx next build"}),
    ("next.config.ts", "Next.js", {"build": "npx next build"}),
    ("vite.config.ts", "Vite", {"build": "npx vite build"}),
    ("vite.config.js", "Vite", {"build": "npx vite build"}),
    ("angular.json", "Angular", {"build": "npx ng build --configuration production"}),
    ("nuxt.config.ts", "Nuxt", {"build": "npx nuxt build"}),
    ("svelte.config.js", "Svelte", {"build": "npm run build"}),
    ("requirements.txt", "Python (pip)", {
        "install": "pip install -r requirements.txt", "test": "pytest -q",
        "lint": "ruff check .", "typecheck": "mypy .", "audit": "pip-audit"}),
    ("pyproject.toml", "Python (pyproject)", {
        "install": "pip install -e .", "test": "pytest -q",
        "lint": "ruff check .", "typecheck": "mypy ."}),
    ("poetry.lock", "Poetry", {"install": "poetry install --sync"}),
    ("manage.py", "Django", {
        "test": "python manage.py test", "migrate": "python manage.py migrate",
        "check": "python manage.py check --deploy", "start": "python manage.py runserver"}),
    ("go.mod", "Go", {
        "build": "go build ./...", "test": "go test ./...", "lint": "golangci-lint run",
        "audit": "govulncheck ./..."}),
    ("Cargo.toml", "Rust", {
        "build": "cargo build --release", "test": "cargo test",
        "lint": "cargo clippy -- -D warnings", "audit": "cargo audit"}),
    ("pom.xml", "Java (Maven)", {
        "build": "mvn -B package", "test": "mvn -B test",
        "audit": "mvn org.owasp:dependency-check-maven:check"}),
    ("build.gradle", "Java/Kotlin (Gradle)", {"build": "./gradlew build", "test": "./gradlew test"}),
    ("build.gradle.kts", "Kotlin (Gradle)", {"build": "./gradlew build", "test": "./gradlew test"}),
    ("Gemfile", "Ruby", {"install": "bundle install", "test": "bundle exec rspec",
                          "audit": "bundle audit check --update"}),
    ("composer.json", "PHP", {"install": "composer install", "test": "vendor/bin/phpunit",
                               "audit": "composer audit"}),
    ("pubspec.yaml", "Dart / Flutter", {
        "build": "flutter build apk --release", "test": "flutter test",
        "lint": "flutter analyze"}),
    ("Package.swift", "Swift", {"build": "swift build -c release", "test": "swift test"}),
    ("mix.exs", "Elixir", {"build": "mix compile --warnings-as-errors", "test": "mix test"}),
    ("Dockerfile", "Docker", {"build": "docker build -t app:rc ."}),
    ("docker-compose.yml", "Docker Compose", {"start": "docker compose up -d"}),
    ("compose.yaml", "Docker Compose", {"start": "docker compose up -d"}),
    ("prisma/schema.prisma", "Prisma ORM", {
        "migrate": "npx prisma migrate deploy", "migrate_reset": "npx prisma migrate reset --force"}),
    ("alembic.ini", "Alembic migrations", {
        "migrate": "alembic upgrade head", "rollback": "alembic downgrade -1"}),
    ("playwright.config.ts", "Playwright E2E", {"e2e": "npx playwright test"}),
    ("playwright.config.js", "Playwright E2E", {"e2e": "npx playwright test"}),
    ("cypress.config.ts", "Cypress E2E", {"e2e": "npx cypress run"}),
    ("terraform", "Terraform", {"plan": "terraform plan"}),
    (".github/workflows", "GitHub Actions CI", {}),
    (".gitlab-ci.yml", "GitLab CI", {}),
]

PROFILE_HINTS = [
    (["package.json", "next.config.js", "next.config.mjs", "index.html", "public"], "web"),
    (["tsconfig.json", "src/app", "src/pages", "app", "components"], "ui"),
    (["prisma/schema.prisma", "alembic.ini", "migrations", "manage.py", "db"], "db"),
    (["openapi.yaml", "openapi.json", "swagger.json", "routes", "api", "controllers"], "api"),
    (["pubspec.yaml", "android", "ios", "Package.swift"], "mobile"),
    (["terraform", "Dockerfile", "docker-compose.yml", "k8s", "helm", ".github/workflows"], "cloud"),
]


def detect(root):
    found, commands = [], {}
    for marker, label, cmds in DETECTORS:
        if os.path.exists(os.path.join(root, marker)):
            found.append({"marker": marker, "label": label})
            for k, v in cmds.items():
                commands.setdefault(k, v)
    hints = set()
    for markers, tag in PROFILE_HINTS:
        for m in markers:
            if os.path.exists(os.path.join(root, m)):
                hints.add(tag)
                break
    # Package.json script mining beats guessing.
    pj = os.path.join(root, "package.json")
    if os.path.isfile(pj):
        try:
            with open(pj, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            scripts = data.get("scripts") or {}
            for key, names in (
                ("build", ["build"]), ("test", ["test"]), ("lint", ["lint"]),
                ("typecheck", ["typecheck", "type-check", "tsc"]),
                ("e2e", ["e2e", "test:e2e"]), ("start", ["start", "serve"]),
                ("format", ["format", "format:check", "fmt"]),
            ):
                for n in names:
                    if n in scripts:
                        commands[key] = "npm run %s" % n
                        break
        except Exception:
            pass
    return found, commands, sorted(hints)


def env_fingerprint(root):
    return {
        "captured_at": now_iso(),
        "host": platform.node(),
        "os": "%s %s (%s)" % (platform.system(), platform.release(), platform.machine()),
        "python": platform.python_version(),
        "cwd": root,
        "git_commit": git(root, "rev-parse", "HEAD"),
        "git_branch": git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "git_describe": git(root, "describe", "--tags", "--always", "--dirty"),
        "git_dirty": bool(git(root, "status", "--porcelain")),
    }


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_init(args):
    root = os.path.abspath(args.root or os.getcwd())
    kit = Kit(root)
    if kit.exists() and not args.force:
        die("%s already initialised. Use --force to reset (evidence is preserved)."
            % os.path.join(root, DIRNAME))

    found, commands, hints = detect(root)
    profile = [p.strip() for p in (args.profile or "").split(",") if p.strip()]
    if not profile:
        profile = hints or ["always"]
    unknown = [p for p in profile if p not in TAGS]
    if unknown:
        die("unknown profile tag(s): %s\nvalid: %s" % (", ".join(unknown), ", ".join(sorted(TAGS))))

    for d in (kit.dir, kit.evidence_dir, kit.attach_dir, kit.report_dir):
        os.makedirs(d, exist_ok=True)

    old_results = {}
    if kit.exists():
        try:
            with open(kit.state_path, "r", encoding="utf-8") as fh:
                old_results = (json.load(fh) or {}).get("results", {})
        except Exception:
            pass

    kit.state = {
        "schema": SCHEMA,
        "project": {
            "name": args.name or os.path.basename(root) or "unnamed",
            "version": args.version or "",
            "root": root,
            "profile": profile,
            "created": now_iso(),
            "owner": args.owner or "",
        },
        "env": env_fingerprint(root),
        "detected": {"stack": found, "suggested_commands": commands, "profile_hints": hints},
        "results": old_results,
        "log": [],
    }
    kit.audit("init", {"profile": profile, "detected": [f["label"] for f in found]})
    kit.save()

    applicable = kit.applicable_checks()
    s0 = [x for x in applicable if x[2] == "S0"]
    print(bold("Launch Readiness Kit initialised."))
    print("  project   : %s%s" % (kit.state["project"]["name"],
                                  (" v" + args.version) if args.version else ""))
    print("  root      : %s" % root)
    print("  profile   : %s" % ", ".join(profile))
    print("  git       : %s @ %s%s" % (kit.state["env"]["git_branch"] or "(no git)",
                                       (kit.state["env"]["git_commit"] or "-")[:12],
                                       "  DIRTY" if kit.state["env"]["git_dirty"] else ""))
    print()
    if found:
        print(bold("Detected stack"))
        for f in found:
            print("  - %-28s (%s)" % (f["label"], f["marker"]))
    else:
        print(yellow("  No known stack markers found -- you must supply commands manually."))
    print()
    if commands:
        print(bold("Suggested commands  ") + dim("(VERIFY EACH ONE ACTUALLY RUNS -- check G0.03)"))
        for k in sorted(commands):
            print("  %-12s %s" % (k, commands[k]))
    print()
    print(bold("Scope: %d of %d checks apply to this profile (%d are S0 blockers)."
               % (len(applicable), len(CATALOG), len(s0))))
    print(dim("Next: python lrk.py checklist --todo"))


def cmd_detect(args):
    root = find_root(args.root)
    found, commands, hints = detect(root)
    print(bold("Root: ") + root)
    print(bold("\nStack markers"))
    for f in found or []:
        print("  - %-28s (%s)" % (f["label"], f["marker"]))
    if not found:
        print("  (none)")
    print(bold("\nSuggested profile tags: ") + (", ".join(hints) or "(none)"))
    print(bold("\nSuggested commands"))
    for k in sorted(commands):
        print("  %-12s %s" % (k, commands[k]))
    print(dim("\nThese are GUESSES. G0.03 requires you to prove each one runs."))


def cmd_profile(args):
    kit = Kit(find_root(args.root))
    kit.load()
    if args.set:
        profile = [p.strip() for p in args.set.split(",") if p.strip()]
        unknown = [p for p in profile if p not in TAGS]
        if unknown:
            die("unknown tag(s): %s" % ", ".join(unknown))
        kit.state["project"]["profile"] = profile
        kit.audit("profile", {"profile": profile})
        kit.save()
    print(bold("Profile: ") + ", ".join(kit.state["project"]["profile"]))
    print()
    for t in sorted(TAGS):
        mark = green(" ON") if t in kit.profile() else dim("off")
        print("  %s  %-12s %s" % (mark, t, TAGS[t]))
    print()
    print("Applicable checks: %d of %d" % (len(kit.applicable_checks()), len(CATALOG)))


def _check_meta(cid):
    for item in CATALOG:
        if item[0] == cid:
            return item
    return None


def cmd_run(args, raw_command):
    kit = Kit(find_root(args.root))
    kit.load()
    meta = _check_meta(args.check_id)
    if not meta:
        die("unknown check id %r. Run `lrk.py checklist` to see valid ids." % args.check_id)
    if not raw_command:
        die("no command given. Usage: lrk.py run %s -- <command>" % args.check_id)

    cid, title, sev, tags, mode = meta
    if args.expect_fail and args.expect_empty:
        die("--expect-fail and --expect-empty are mutually exclusive.")

    shell_exe, shell_name = resolve_shell(args.shell)
    command = (raw_command if isinstance(raw_command, str)
               else rejoin(raw_command, shell_name))
    cwd = os.path.abspath(args.cwd) if args.cwd else kit.root

    check_dir = os.path.join(kit.evidence_dir, cid)
    os.makedirs(check_dir, exist_ok=True)
    seq = len([f for f in os.listdir(check_dir) if f.endswith(".log")]) + 1
    log_name = "%02d-%s.log" % (seq, slugify(args.title or command))
    log_path = os.path.join(check_dir, log_name)

    print(dim("$ ") + command)
    started_wall = now_iso()
    t0 = time.time()
    timed_out = False
    try:
        # Build the invocation explicitly. subprocess's `executable=` does not work
        # for bash on Windows: shell=True still supplies cmd.exe's `/c` flag, which
        # bash reads as a script path ("/c: Is a directory").
        if shell_name == "bash":
            spec, use_shell = [shell_exe, "-c", command], False
        elif shell_name == "cmd":
            spec, use_shell = [shell_exe, "/c", command], False
        else:
            spec, use_shell = command, True
        proc = subprocess.run(
            spec, shell=use_shell, cwd=cwd, capture_output=True, timeout=args.timeout
        )
        out = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as te:
        timed_out = True
        out = (te.stdout or b"").decode("utf-8", "replace")
        err = (te.stderr or b"").decode("utf-8", "replace")
        exit_code = 124
    except Exception as exc:
        out, err, exit_code = "", "lrk could not launch the command: %s" % exc, 127
    duration_ms = int((time.time() - t0) * 1000)

    header = (
        "==============================================================================\n"
        "LAUNCH READINESS EVIDENCE\n"
        "==============================================================================\n"
        "check        : %s  %s\n"
        "title        : %s\n"
        "severity     : %s\n"
        "command      : %s\n"
        "shell        : %s\n"
        "working dir  : %s\n"
        "started      : %s\n"
        "duration     : %d ms%s\n"
        "pass rule    : %s\n"
        "exit code    : %d\n"
        "host         : %s  |  %s\n"
        "git commit   : %s (%s)%s\n"
        "==============================================================================\n"
        % (cid, args.title or title, title, "%s %s" % (sev, SEVERITIES[sev]),
           command, "%s (%s)" % (shell_name, shell_exe or "system default"),
           cwd, started_wall, duration_ms,
           "  (TIMED OUT after %ss)" % args.timeout if timed_out else "",
           ("PASS when the command finds NOTHING (empty stdout)" if args.expect_empty
            else "PASS when the exit code is NON-ZERO (negative/sabotage test)"
            if args.expect_fail else "PASS when the exit code is 0"),
           exit_code, platform.node(),
           "%s %s" % (platform.system(), platform.release()),
           (git(kit.root, "rev-parse", "HEAD") or "-")[:12],
           git(kit.root, "rev-parse", "--abbrev-ref", "HEAD") or "-",
           "  DIRTY" if git(kit.root, "status", "--porcelain") else "")
    )
    body = "----- STDOUT -----\n%s\n----- STDERR -----\n%s\n" % (out, err)
    with open(log_path, "w", encoding="utf-8", errors="replace") as fh:
        fh.write(header + body)

    digest = sha256_file(log_path)

    if args.expect_empty:
        # For scan checks: finding nothing is the pass. Independent of the tool's
        # exit-code convention -- grep exits 0 when it FINDS something, which would
        # otherwise record "secrets found" as a pass.
        hits = [ln for ln in out.splitlines() if ln.strip()]
        # grep-family convention: 0 = found matches, 1 = found none, >1 = it broke.
        # A command that never ran also tends to exit non-zero with text on stderr,
        # and MUST NOT be recorded as "found nothing" -- that would turn a broken
        # secret scan into a green tick.
        scan_ran = exit_code == 0 or (exit_code == 1 and not err.strip())
        if not scan_ran:
            ok = False
            verdict_reason = ("scan did not run correctly (exit %d%s) -- a scan that "
                              "cannot run is NOT a clean scan"
                              % (exit_code, "; stderr present" if err.strip() else ""))
        elif hits:
            ok = False
            verdict_reason = "expected no findings; found %d line(s)" % len(hits)
        else:
            ok = True
            verdict_reason = "expected no findings; scan ran and found none"
    elif args.expect_fail:
        ok = exit_code != 0
        verdict_reason = "expected a NON-ZERO exit (sabotage/negative test); got %d" % exit_code
    else:
        ok = exit_code == 0
        verdict_reason = "expected exit 0; got %d" % exit_code

    r = kit.result(cid)
    r["records"].append({
        "kind": "cmd",
        "at": started_wall,
        "title": args.title or "",
        "command": command,
        "cwd": cwd,
        "shell": shell_name,
        "exit": exit_code,
        "expect_fail": bool(args.expect_fail),
        "expect_empty": bool(args.expect_empty),
        "rule": verdict_reason,
        "ok": ok,
        "duration_ms": duration_ms,
        "timed_out": timed_out,
        "log": os.path.relpath(log_path, kit.dir).replace("\\", "/"),
        "sha256": digest,
        "bytes": os.path.getsize(log_path),
        "note": args.note or "",
    })
    if args.record_only:
        r["status"] = r.get("status", "todo")
    else:
        r["status"] = "pass" if ok else "fail"
    r["updated"] = now_iso()
    kit.recompute_proof(cid)
    kit.audit("run", {"check": cid, "exit": exit_code, "ok": ok, "log": log_name})
    kit.save()

    tail = "\n".join((out or err).splitlines()[-args.tail:]) if args.tail else ""
    if tail:
        print(dim(tail))
    badge = green("PASS") if ok else red("FAIL")
    if args.record_only:
        badge = yellow("RECORDED")
    print("%s  %s  %s  (%s, %d ms)" % (badge, cid, title, verdict_reason, duration_ms))
    print(dim("  evidence: %s" % os.path.relpath(log_path, kit.root)))
    print(dim("  sha256  : %s" % digest))
    if not ok and not args.record_only:
        raise SystemExit(1)


def cmd_manual(args):
    kit = Kit(find_root(args.root))
    kit.load()
    meta = _check_meta(args.check_id)
    if not meta:
        die("unknown check id %r." % args.check_id)
    cid, title, sev, tags, mode = meta
    status = args.status
    if status not in ("pass", "fail", "na", "todo"):
        die("status must be one of: pass, fail, na, todo (use `waive` for waivers).")
    if status == "na" and not args.note:
        die("N/A requires --note explaining WHY this check does not apply.")
    if status == "pass" and not args.note:
        die("A manual pass requires --note describing exactly what was observed.")

    r = kit.result(cid)
    r["records"].append({
        "kind": "note", "at": now_iso(), "status": status,
        "text": args.note or "", "by": args.by or "",
    })
    if args.attach:
        _attach_file(kit, cid, args.attach, args.caption or "")
    r["status"] = status
    r["updated"] = now_iso()
    proof = kit.recompute_proof(cid)
    kit.audit("manual", {"check": cid, "status": status})
    kit.save()

    badge = {"pass": green("PASS"), "fail": red("FAIL"),
             "na": dim("N/A "), "todo": yellow("TODO")}[status]
    print("%s  %s  %s" % (badge, cid, title))
    if mode == "cmd" and status == "pass" and proof != "executed":
        print(red("  WARNING: this check's mode is `cmd`. A written note is NOT sufficient proof."))
        print(red("  It will appear as ASSERTED in the report and will block a GO certificate"
                  " if it is S0."))
    elif mode == "manual" and status == "pass" and proof == "asserted":
        if sev == "S0":
            print(red("  This is an S0 and it has no attachment. It will be reported as"
                      " ASSERTED WITHOUT PROOF and counted as a BLOCKER."))
            print(red("  Write what you just described into a file and attach it:"))
            print(red("    python lrk.py attach %s <file>" % cid))
        else:
            print(yellow("  Note: no attachment. Manual checks are far stronger with a screenshot,"
                         " log, or document -- use `lrk.py attach %s <file>`." % cid))


def _attach_file(kit, cid, path, caption):
    src = os.path.abspath(path)
    if not os.path.isfile(src):
        die("attachment not found: %s" % src)
    dest_dir = os.path.join(kit.attach_dir, cid)
    os.makedirs(dest_dir, exist_ok=True)
    base = os.path.basename(src)
    dest = os.path.join(dest_dir, base)
    n = 1
    while os.path.exists(dest):
        stem, ext = os.path.splitext(base)
        dest = os.path.join(dest_dir, "%s-%d%s" % (stem, n, ext))
        n += 1
    shutil.copy2(src, dest)
    digest = sha256_file(dest)
    kit.result(cid)["records"].append({
        "kind": "attach", "at": now_iso(),
        "file": os.path.relpath(dest, kit.dir).replace("\\", "/"),
        "original": src, "caption": caption,
        "sha256": digest, "bytes": os.path.getsize(dest),
    })
    return dest, digest


def cmd_attach(args):
    kit = Kit(find_root(args.root))
    kit.load()
    if not _check_meta(args.check_id):
        die("unknown check id %r." % args.check_id)
    dest, digest = _attach_file(kit, args.check_id, args.file, args.caption or "")
    kit.recompute_proof(args.check_id)
    kit.result(args.check_id)["updated"] = now_iso()
    kit.audit("attach", {"check": args.check_id, "file": os.path.basename(dest)})
    kit.save()
    print(green("ATTACHED") + "  %s  <- %s" % (args.check_id, os.path.basename(dest)))
    print(dim("  sha256: %s" % digest))


def cmd_waive(args):
    kit = Kit(find_root(args.root))
    kit.load()
    meta = _check_meta(args.check_id)
    if not meta:
        die("unknown check id %r." % args.check_id)
    cid, title, sev, tags, mode = meta
    if sev == "S0" and not args.accept_blocker_risk:
        die("%s is an S0 BLOCKER. S0 checks are not waivable by default.\n"
            "If the owner is knowingly accepting this risk, re-run with "
            "--accept-blocker-risk. It will be printed in red on the certificate." % cid)
    for field, name in ((args.by, "--by"), (args.reason, "--reason"), (args.risk, "--risk")):
        if not field:
            die("%s is required for a waiver." % name)
    r = kit.result(cid)
    r["status"] = "waived"
    r["waiver"] = {
        "by": args.by, "reason": args.reason, "risk": args.risk,
        "expires": args.expires or "", "at": now_iso(),
        "blocker_override": bool(args.accept_blocker_risk and sev == "S0"),
    }
    r["updated"] = now_iso()
    kit.recompute_proof(cid)
    kit.audit("waive", {"check": cid, "by": args.by, "severity": sev})
    kit.save()
    print(yellow("WAIVED") + "  %s  %s" % (cid, title))
    print("  by     : %s" % args.by)
    print("  risk   : %s" % args.risk)
    if sev == "S0":
        print(red("  This is a BLOCKER override. The certificate will say NO-GO"
                  " unless the owner signs it explicitly."))


def _rows(kit, gate_filter=None, todo_only=False):
    rows = []
    for cid, title, sev, tags, mode in CATALOG:
        g = gate_of(cid)
        if gate_filter and g != gate_filter.upper():
            continue
        app = kit.applicable(tags)
        r = kit.state.get("results", {}).get(cid)
        status = (r or {}).get("status", "todo")
        proof = (r or {}).get("proof", "none")
        if not app and status == "todo":
            status, proof = "na", "none"
        if todo_only and status not in ("todo", "fail"):
            continue
        rows.append({
            "id": cid, "gate": g, "title": title, "sev": sev, "tags": tags,
            "mode": mode, "applicable": app, "status": status, "proof": proof,
            "records": (r or {}).get("records", []), "waiver": (r or {}).get("waiver"),
            "updated": (r or {}).get("updated"),
        })
    return rows


def _verdict(rows):
    """Return (verdict, blockers, warnings) computed purely from the data."""
    blockers, warnings = [], []
    for row in rows:
        if not row["applicable"]:
            continue
        st, sev, proof = row["status"], row["sev"], row["proof"]
        if st == "na":
            continue
        if sev == "S0":
            if st == "fail":
                blockers.append((row, "FAILING"))
            elif st == "todo":
                blockers.append((row, "NOT TESTED"))
            elif st == "waived":
                blockers.append((row, "BLOCKER WAIVED"))
            elif st == "pass" and proof == "asserted":
                blockers.append((row, "ASSERTED WITHOUT PROOF"))
            elif st == "pass" and proof == "none":
                blockers.append((row, "NO EVIDENCE RECORDED"))
        elif sev == "S1":
            if st == "fail":
                warnings.append((row, "FAILING"))
            elif st == "todo":
                warnings.append((row, "NOT TESTED"))
            elif st == "pass" and proof in ("asserted", "none"):
                warnings.append((row, "WEAK EVIDENCE"))
        else:
            if st == "fail":
                warnings.append((row, "FAILING (minor)"))
    verdict = "NO-GO" if blockers else ("GO WITH CONDITIONS" if warnings else "GO")
    return verdict, blockers, warnings


def cmd_status(args):
    kit = Kit(find_root(args.root))
    kit.load()
    rows = _rows(kit, args.gate)
    app = [r for r in rows if r["applicable"]]
    counts = {}
    for r in app:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    verdict, blockers, warnings = _verdict(_rows(kit))

    print(bold("%s%s") % (kit.state["project"]["name"],
                          (" v" + kit.state["project"]["version"])
                          if kit.state["project"]["version"] else ""))
    print(dim("root %s   profile %s" % (kit.root, ", ".join(kit.state["project"]["profile"]))))
    print()

    gates = sorted({r["gate"] for r in rows}, key=lambda g: int(g[1:]))
    gate_names = {g[0]: g[1] for g in GATES}
    for g in gates:
        grows = [r for r in rows if r["gate"] == g and r["applicable"]]
        if not grows:
            continue
        done = len([r for r in grows if r["status"] in ("pass", "na", "waived")])
        failed = len([r for r in grows if r["status"] == "fail"])
        total = len(grows)
        pct = int(100 * done / total) if total else 100
        bar_w = 24
        filled = int(bar_w * done / total) if total else bar_w
        bar = "#" * filled + "." * (bar_w - filled)
        colour = green if (done == total and not failed) else (red if failed else yellow)
        print("%s %-4s %s %3d%%  %2d/%-2d  %s%s" % (
            colour("|"), g, bar, pct, done, total, gate_names.get(g, ""),
            red("  %d FAILING" % failed) if failed else ""))

    print()
    print("  " + "   ".join(
        "%s %d" % (k, counts.get(k, 0)) for k in ("pass", "fail", "todo", "waived", "na")))
    print()
    banner = {"GO": green, "GO WITH CONDITIONS": yellow, "NO-GO": red}[verdict]
    print(banner(bold("  VERDICT: %s" % verdict)))
    if blockers:
        print(red("  %d blocker(s):" % len(blockers)))
        for row, why in blockers[:12]:
            print(red("    %-8s %-24s %s" % (row["id"], why, row["title"][:64])))
        if len(blockers) > 12:
            print(red("    ... and %d more" % (len(blockers) - 12)))
    if warnings and args.verbose:
        print(yellow("  %d warning(s):" % len(warnings)))
        for row, why in warnings:
            print(yellow("    %-8s %-24s %s" % (row["id"], why, row["title"][:64])))
    elif warnings:
        print(yellow("  %d warning(s) -- run with --verbose to list them." % len(warnings)))


def cmd_checklist(args):
    kit = Kit(find_root(args.root))
    kit.load()
    rows = _rows(kit, args.gate, args.todo)
    gate_names = {g[0]: (g[1], g[2], g[3]) for g in GATES}
    if args.md:
        print("# Launch Readiness Checklist -- %s" % kit.state["project"]["name"])
        print("\nGenerated %s. Profile: %s\n" % (today(), ", ".join(kit.state["project"]["profile"])))
        cur = None
        for r in rows:
            if r["gate"] != cur:
                cur = r["gate"]
                name, purpose, veto = gate_names[cur]
                print("\n## %s -- %s\n\n> %s  \n> Veto holder: **%s**\n" % (cur, name, purpose, veto))
                print("| ID | Sev | Mode | Status | Check |")
                print("|---|---|---|---|---|")
            box = {"pass": "PASS", "fail": "FAIL", "todo": "todo",
                   "na": "n/a", "waived": "WAIVED"}[r["status"]]
            print("| `%s` | %s | %s | %s | %s |" % (r["id"], r["sev"], r["mode"], box, r["title"]))
        return

    cur = None
    for r in rows:
        if r["gate"] != cur:
            cur = r["gate"]
            name, purpose, veto = gate_names[cur]
            print()
            print(bold("%s  %s" % (cur, name)))
            print(dim("     %s  |  veto: %s" % (purpose, veto)))
        badge = {"pass": green("[PASS]"), "fail": red("[FAIL]"), "todo": yellow("[    ]"),
                 "na": dim("[ n/a]"), "waived": yellow("[WAIV]")}[r["status"]]
        sev = {"S0": red("S0"), "S1": yellow("S1"), "S2": "S2", "S3": dim("S3")}[r["sev"]]
        pr = {"executed": green("exec"), "attached": green("attd"),
              "asserted": yellow("said"), "none": dim("  - ")}[r["proof"]]
        line = "  %s %s %s %-8s %s" % (badge, sev, pr, r["id"], r["title"])
        print(line if r["applicable"] else dim(line))
    print()
    print(dim("legend: exec=proven by a recorded command, attd=proven by an attached file,"
              " said=asserted only"))


def cmd_verify(args):
    kit = Kit(find_root(args.root))
    kit.load()
    bad, ok, missing = [], 0, []
    for cid, r in kit.state.get("results", {}).items():
        for rec in r.get("records", []):
            rel = rec.get("log") or rec.get("file")
            if not rel:
                continue
            path = os.path.join(kit.dir, rel)
            if not os.path.isfile(path):
                missing.append((cid, rel))
                continue
            if sha256_file(path) != rec.get("sha256"):
                bad.append((cid, rel))
            else:
                ok += 1
    print(bold("Evidence integrity"))
    print("  verified  : %d file(s) match their recorded hash" % ok)
    if missing:
        print(red("  MISSING   : %d" % len(missing)))
        for cid, rel in missing:
            print(red("    %s  %s" % (cid, rel)))
    if bad:
        print(red("  TAMPERED  : %d -- content changed after it was recorded" % len(bad)))
        for cid, rel in bad:
            print(red("    %s  %s" % (cid, rel)))
    if not missing and not bad:
        print(green("  OK -- no evidence file has been altered since it was recorded."))
        return
    raise SystemExit(1)


def _write_manifest(kit):
    lines = []
    for base in (kit.evidence_dir, kit.attach_dir):
        for dirpath, _dirs, files in os.walk(base):
            for f in sorted(files):
                p = os.path.join(dirpath, f)
                lines.append("%s  %s" % (sha256_file(p),
                                         os.path.relpath(p, kit.dir).replace("\\", "/")))
    if os.path.isfile(kit.state_path):
        lines.append("%s  state.json" % sha256_file(kit.state_path))
    path = os.path.join(kit.report_dir, "MANIFEST.sha256")
    os.makedirs(kit.report_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Launch Readiness evidence manifest -- generated %s\n" % now_iso())
        fh.write("# Verify with: python lrk.py verify\n")
        fh.write("\n".join(sorted(lines)) + "\n")
    return path, len(lines)


def cmd_certify(args):
    kit = Kit(find_root(args.root))
    kit.load()
    rows = _rows(kit)
    verdict, blockers, warnings = _verdict(rows)
    proj = kit.state["project"]
    env = env_fingerprint(kit.root)
    app = [r for r in rows if r["applicable"]]
    executed = len([r for r in app if r["proof"] == "executed"])
    attached = len([r for r in app if r["proof"] == "attached"])
    asserted = len([r for r in app if r["proof"] == "asserted"])

    L = []
    L.append("# Launch Readiness Certificate")
    L.append("")
    L.append("    %s" % ("*" * 66))
    L.append("    VERDICT: %s" % verdict)
    L.append("    %s" % ("*" * 66))
    L.append("")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| Product | %s |" % proj["name"])
    L.append("| Version | %s |" % (proj["version"] or "(unversioned -- see G11.01)"))
    L.append("| Owner | %s |" % (proj["owner"] or "(unnamed -- see G11.13)"))
    L.append("| Profile | %s |" % ", ".join(proj["profile"]))
    L.append("| Git commit | `%s` |" % (env["git_commit"] or "no git"))
    L.append("| Git branch | %s%s |" % (env["git_branch"] or "-",
                                        "  **WORKING TREE DIRTY**" if env["git_dirty"] else ""))
    L.append("| Certified at | %s |" % now_iso())
    L.append("| Host | %s / %s |" % (env["host"], env["os"]))
    L.append("")
    L.append("## Coverage")
    L.append("")
    L.append("| Metric | Count |")
    L.append("|---|---|")
    L.append("| Checks in catalogue | %d |" % len(CATALOG))
    L.append("| Applicable to this profile | %d |" % len(app))
    L.append("| Passed | %d |" % len([r for r in app if r["status"] == "pass"]))
    L.append("| Failed | %d |" % len([r for r in app if r["status"] == "fail"]))
    L.append("| Not tested | %d |" % len([r for r in app if r["status"] == "todo"]))
    L.append("| Waived | %d |" % len([r for r in app if r["status"] == "waived"]))
    L.append("| Not applicable | %d |" % len([r for r in app if r["status"] == "na"]))
    L.append("")
    L.append("### Strength of proof")
    L.append("")
    L.append("| Level | Count | Meaning |")
    L.append("|---|---|---|")
    L.append("| Executed | %d | Proven by a recorded command, with raw output and a hash |" % executed)
    L.append("| Attached | %d | Proven by an attached artifact (screenshot, log, document) |" % attached)
    L.append("| Asserted | %d | Somebody wrote that it was fine. Weakest form of evidence. |" % asserted)
    L.append("")

    if blockers:
        L.append("## BLOCKERS -- launch is forbidden while these are open")
        L.append("")
        L.append("| ID | Reason | Check |")
        L.append("|---|---|---|")
        for row, why in blockers:
            L.append("| `%s` | **%s** | %s |" % (row["id"], why, row["title"]))
        L.append("")
    else:
        L.append("## Blockers")
        L.append("")
        L.append("None. Every applicable S0 check passed with recorded evidence.")
        L.append("")

    if warnings:
        L.append("## Warnings -- fix, or accept in writing")
        L.append("")
        L.append("| ID | Reason | Check |")
        L.append("|---|---|---|")
        for row, why in warnings:
            L.append("| `%s` | %s | %s |" % (row["id"], why, row["title"]))
        L.append("")

    waived = [r for r in app if r["status"] == "waived"]
    if waived:
        L.append("## Waivers on record")
        L.append("")
        for r in waived:
            w = r["waiver"] or {}
            L.append("**%s (%s)** -- %s" % (r["id"], r["sev"], r["title"]))
            L.append("")
            L.append("- Waived by: %s on %s" % (w.get("by", "?"), (w.get("at") or "")[:10]))
            L.append("- Reason: %s" % w.get("reason", ""))
            L.append("- Risk accepted: %s" % w.get("risk", ""))
            if w.get("expires"):
                L.append("- Expires: %s" % w["expires"])
            L.append("")

    L.append("## Signature block")
    L.append("")
    L.append("This certificate was computed from recorded evidence, not from anyone's opinion.")
    L.append("Verify the evidence has not been altered:")
    L.append("")
    L.append("```")
    L.append("python lrk.py verify")
    L.append("```")
    L.append("")
    L.append("| Role | Name | Date | Decision |")
    L.append("|---|---|---|---|")
    L.append("| Engineering owner |  |  |  |")
    L.append("| Security reviewer |  |  |  |")
    L.append("| Operations / SRE |  |  |  |")
    L.append("| Product owner (final GO) |  |  |  |")
    L.append("")
    if verdict == "NO-GO":
        L.append("> A NO-GO certificate may only be overridden by the product owner signing")
        L.append("> above **and** writing, in one sentence per blocker, the risk being accepted")
        L.append("> and who will be woken up when it happens.")

    path = os.path.join(kit.dir, "CERTIFICATE.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    kit.state["last_certificate"] = {"at": now_iso(), "verdict": verdict,
                                     "blockers": len(blockers), "warnings": len(warnings)}
    kit.audit("certify", {"verdict": verdict, "blockers": len(blockers)})
    kit.save()

    banner = {"GO": green, "GO WITH CONDITIONS": yellow, "NO-GO": red}[verdict]
    print(banner(bold("VERDICT: %s" % verdict)))
    print("  blockers %d   warnings %d" % (len(blockers), len(warnings)))
    print("  written  : %s" % path)
    if verdict == "NO-GO":
        raise SystemExit(1)


# --------------------------------------------------------------------------
# HTML report
# --------------------------------------------------------------------------

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
MAX_EMBED_ONE = 3 * 1024 * 1024
MAX_EMBED_TOTAL = 10 * 1024 * 1024
MAX_LOG_CHARS = 120000

CSS = """
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1a1a18;--muted:#6b6b66;--line:#e3e3de;
--pass:#1a7f4b;--fail:#c0332e;--warn:#a8690a;--na:#8a8a84;--accent:#2b5fd9;
--passbg:#e9f5ee;--failbg:#fbeceb;--warnbg:#fdf3e3;--code:#f1f1ee;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#151513;--panel:#1e1e1c;--ink:#eceae4;--muted:#9a9a93;--line:#33332f;
--pass:#5fcf92;--fail:#f0736c;--warn:#e0a63f;--na:#7d7d76;--accent:#7aa2f7;
--passbg:#17281f;--failbg:#2c1817;--warnbg:#2a2113;--code:#141412;}}
:root[data-theme="dark"]{--bg:#151513;--panel:#1e1e1c;--ink:#eceae4;--muted:#9a9a93;
--line:#33332f;--pass:#5fcf92;--fail:#f0736c;--warn:#e0a63f;--na:#7d7d76;--accent:#7aa2f7;
--passbg:#17281f;--failbg:#2c1817;--warnbg:#2a2113;--code:#141412;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:1080px;margin:0 auto;padding:32px 20px 96px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:19px;margin:38px 0 12px;letter-spacing:-.01em}
h3{font-size:15px;margin:0}
.sub{color:var(--muted);font-size:13px;margin-bottom:24px}
.verdict{border-radius:12px;padding:22px 24px;margin:20px 0 28px;border:2px solid;}
.verdict .v{font-size:34px;font-weight:800;letter-spacing:-.03em;line-height:1}
.verdict .d{margin-top:8px;font-size:14px;opacity:.85}
.v-GO{background:var(--passbg);border-color:var(--pass);color:var(--pass)}
.v-COND{background:var(--warnbg);border-color:var(--warn);color:var(--warn)}
.v-NOGO{background:var(--failbg);border-color:var(--fail);color:var(--fail)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card .n{font-size:24px;font-weight:700;letter-spacing:-.02em}
.card .l{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-top:2px}
table{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--panel);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
background:var(--code);font-weight:600}
tr:last-child td{border-bottom:none}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;font-weight:700;
letter-spacing:.04em;white-space:nowrap}
.p-pass{background:var(--passbg);color:var(--pass)}
.p-fail{background:var(--failbg);color:var(--fail)}
.p-todo{background:var(--warnbg);color:var(--warn)}
.p-na{background:var(--code);color:var(--na)}
.p-waived{background:var(--warnbg);color:var(--warn)}
.sev{font-weight:700;font-size:11px}
.s-S0{color:var(--fail)} .s-S1{color:var(--warn)} .s-S2{color:var(--muted)} .s-S3{color:var(--na)}
.proof{font-size:11px;font-weight:600;letter-spacing:.03em}
.pr-executed{color:var(--pass)} .pr-attached{color:var(--accent)}
.pr-asserted{color:var(--warn)} .pr-none{color:var(--na)}
details{margin:8px 0 0}
summary{cursor:pointer;font-size:12px;color:var(--accent);user-select:none}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:12px;
overflow-x:auto;font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;
white-space:pre;margin:8px 0}
code{font:12.5px ui-monospace,SFMono-Regular,Consolas,monospace;background:var(--code);
padding:1px 5px;border-radius:4px}
.bar{height:7px;background:var(--code);border-radius:99px;overflow:hidden;min-width:110px}
.bar i{display:block;height:100%;background:var(--pass)}
.bar.has-fail i{background:var(--fail)}
img.shot{max-width:100%;border:1px solid var(--line);border-radius:8px;margin:8px 0;display:block}
.meta{font-size:11.5px;color:var(--muted);font-family:ui-monospace,Consolas,monospace;
word-break:break-all}
.gatehead{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:34px 0 8px}
.gatehead h2{margin:0}
.note{background:var(--panel);border-left:3px solid var(--accent);padding:10px 14px;
border-radius:0 8px 8px 0;margin:8px 0;font-size:13.5px}
.foot{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
color:var(--muted);font-size:12.5px}
"""


def _esc(s):
    return html.escape(s or "", quote=True)


def _read_log(kit, rel, cap=MAX_LOG_CHARS):
    path = os.path.join(kit.dir, rel)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = fh.read()
    except Exception as exc:
        return "(evidence file unreadable: %s)" % exc
    if len(data) > cap:
        head = data[: cap // 2]
        tail = data[-cap // 2:]
        return head + "\n\n... [%d characters omitted from the middle -- full log on disk at %s] ...\n\n" % (
            len(data) - cap, rel) + tail
    return data


def cmd_report(args):
    kit = Kit(find_root(args.root))
    kit.load()
    rows = _rows(kit)
    verdict, blockers, warnings = _verdict(rows)
    proj = kit.state["project"]
    env = env_fingerprint(kit.root)
    app = [r for r in rows if r["applicable"]]
    gate_names = {g[0]: (g[1], g[2], g[3]) for g in GATES}

    integrity_ok, integrity_bad, integrity_missing = 0, [], []
    for cid, r in kit.state.get("results", {}).items():
        for rec in r.get("records", []):
            rel = rec.get("log") or rec.get("file")
            if not rel:
                continue
            p = os.path.join(kit.dir, rel)
            if not os.path.isfile(p):
                integrity_missing.append(rel)
            elif sha256_file(p) != rec.get("sha256"):
                integrity_bad.append(rel)
            else:
                integrity_ok += 1

    embedded_total = [0]

    def render_records(row):
        out = []
        for rec in row["records"]:
            kind = rec.get("kind")
            if kind == "cmd":
                ok = rec.get("ok")
                out.append(
                    '<details><summary>%s &nbsp;<code>%s</code> &nbsp;exit %s &nbsp;(%d ms)</summary>'
                    % ("PASS" if ok else "FAIL", _esc(rec["command"][:160]),
                       rec.get("exit"), rec.get("duration_ms", 0)))
                out.append('<div class="meta">ran %s in %s<br>rule: %s<br>'
                           "sha256 %s &nbsp;&middot;&nbsp; %s</div>"
                           % (_esc(rec.get("at", "")), _esc(rec.get("cwd", "")),
                              _esc(rec.get("rule", "expected exit 0")),
                              _esc(rec.get("sha256", "")), _esc(rec.get("log", ""))))
                out.append("<pre>%s</pre></details>" % _esc(_read_log(kit, rec["log"])))
            elif kind == "note":
                out.append('<div class="note"><strong>%s</strong> &mdash; %s%s</div>'
                           % (_esc((rec.get("status") or "note").upper()), _esc(rec.get("text", "")),
                              (" <span class=\"meta\">(%s)</span>" % _esc(rec["by"]))
                              if rec.get("by") else ""))
            elif kind == "attach":
                rel = rec["file"]
                p = os.path.join(kit.dir, rel)
                ext = os.path.splitext(rel)[1].lower()
                cap = _esc(rec.get("caption") or os.path.basename(rel))
                if (ext in IMAGE_EXT and os.path.isfile(p)
                        and rec.get("bytes", 0) <= MAX_EMBED_ONE
                        and embedded_total[0] + rec.get("bytes", 0) <= MAX_EMBED_TOTAL):
                    try:
                        with open(p, "rb") as fh:
                            b64 = base64.b64encode(fh.read()).decode("ascii")
                        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                                "gif": "image/gif", "webp": "image/webp",
                                "svg": "image/svg+xml"}[ext.lstrip(".")]
                        embedded_total[0] += rec.get("bytes", 0)
                        out.append('<img class="shot" alt="%s" src="data:%s;base64,%s">' % (cap, mime, b64))
                        out.append('<div class="meta">%s &middot; %s &middot; sha256 %s</div>'
                                   % (cap, human_bytes(rec.get("bytes", 0)), _esc(rec.get("sha256", ""))))
                    except Exception:
                        out.append('<div class="meta">attachment %s (could not embed)</div>' % cap)
                elif ext in (".txt", ".log", ".md", ".json", ".csv", ".yaml", ".yml") and os.path.isfile(p):
                    out.append("<details><summary>attachment: %s (%s)</summary><pre>%s</pre>"
                               '<div class="meta">sha256 %s</div></details>'
                               % (cap, human_bytes(rec.get("bytes", 0)),
                                  _esc(_read_log(kit, rel, 40000)), _esc(rec.get("sha256", ""))))
                else:
                    out.append('<div class="meta">attachment: %s &middot; %s &middot; sha256 %s'
                               '<br>on disk at <code>%s</code></div>'
                               % (cap, human_bytes(rec.get("bytes", 0)),
                                  _esc(rec.get("sha256", "")), _esc(rel)))
        if row.get("waiver"):
            w = row["waiver"]
            out.append('<div class="note"><strong>WAIVED</strong> by %s &mdash; %s<br>'
                       "<em>Risk accepted:</em> %s%s</div>"
                       % (_esc(w.get("by", "")), _esc(w.get("reason", "")), _esc(w.get("risk", "")),
                          (" &middot; expires %s" % _esc(w["expires"])) if w.get("expires") else ""))
        if not out:
            out.append('<div class="meta">No evidence recorded.</div>')
        return "\n".join(out)

    vclass = {"GO": "v-GO", "GO WITH CONDITIONS": "v-COND", "NO-GO": "v-NOGO"}[verdict]
    vdesc = {
        "GO": "Every applicable blocker check passed with recorded evidence.",
        "GO WITH CONDITIONS": "No blockers, but there are open major findings listed below. "
                              "Each one needs a fix or a written waiver before you ship.",
        "NO-GO": "At least one blocker check is failing, untested, or claimed without proof. "
                 "Shipping now means shipping a known unknown.",
    }[verdict]

    H = []
    H.append("<title>%s &mdash; Launch Readiness Report</title>" % _esc(proj["name"]))
    H.append("<style>%s</style>" % CSS)
    H.append('<div class="wrap">')
    H.append("<h1>%s%s &mdash; Launch Readiness Report</h1>" % (
        _esc(proj["name"]), (" v" + _esc(proj["version"])) if proj["version"] else ""))
    H.append('<div class="sub">Generated %s &middot; commit <code>%s</code> on %s%s '
             "&middot; host %s &middot; profile: %s</div>"
             % (_esc(now_iso()), _esc((env["git_commit"] or "no-git")[:12]),
                _esc(env["git_branch"] or "-"),
                ' &middot; <strong style="color:var(--fail)">WORKING TREE DIRTY</strong>'
                if env["git_dirty"] else "",
                _esc(env["host"]), _esc(", ".join(proj["profile"]))))

    H.append('<div class="verdict %s"><div class="v">%s</div><div class="d">%s</div></div>'
             % (vclass, _esc(verdict), _esc(vdesc)))

    counts = {k: len([r for r in app if r["status"] == k])
              for k in ("pass", "fail", "todo", "waived", "na")}
    proofs = {k: len([r for r in app if r["proof"] == k])
              for k in ("executed", "attached", "asserted", "none")}
    H.append('<div class="grid">')
    for label, num in (("Applicable", len(app)), ("Passed", counts["pass"]),
                       ("Failed", counts["fail"]), ("Not tested", counts["todo"]),
                       ("Waived", counts["waived"]), ("Blockers open", len(blockers))):
        H.append('<div class="card"><div class="n">%d</div><div class="l">%s</div></div>' % (num, label))
    H.append("</div>")

    H.append("<h2>Strength of proof</h2>")
    H.append('<div class="note">This is the number that matters. <strong>Executed</strong> means a '
             "command really ran and its raw output is stored below. <strong>Asserted</strong> means "
             "somebody typed that it was fine. A report full of assertions is a report of opinions.</div>")
    H.append('<div class="scroll"><table><tr><th>Level</th><th>Count</th><th>What it means</th></tr>')
    for k, meaning in (
        ("executed", "A recorded command ran; stdout, stderr, exit code and a SHA-256 hash are stored."),
        ("attached", "A file was attached as proof: screenshot, report, export, document."),
        ("asserted", "Written claim only. Acceptable for S2/S3; never sufficient for an S0."),
        ("none", "Nothing recorded at all.")):
        H.append("<tr><td><span class='proof pr-%s'>%s</span></td><td>%d</td><td>%s</td></tr>"
                 % (k, k.upper(), proofs[k], meaning))
    H.append("</table></div>")

    if blockers:
        H.append("<h2>Blockers &mdash; launch is forbidden while these are open</h2>")
        H.append('<div class="scroll"><table><tr><th>ID</th><th>Reason</th><th>Check</th></tr>')
        for row, why in blockers:
            H.append("<tr><td><code>%s</code></td><td><span class='pill p-fail'>%s</span></td>"
                     "<td>%s</td></tr>" % (row["id"], _esc(why), _esc(row["title"])))
        H.append("</table></div>")
    if warnings:
        H.append("<h2>Warnings &mdash; fix, or waive in writing</h2>")
        H.append('<div class="scroll"><table><tr><th>ID</th><th>Reason</th><th>Check</th></tr>')
        for row, why in warnings:
            H.append("<tr><td><code>%s</code></td><td><span class='pill p-todo'>%s</span></td>"
                     "<td>%s</td></tr>" % (row["id"], _esc(why), _esc(row["title"])))
        H.append("</table></div>")

    H.append("<h2>Gate summary</h2>")
    H.append('<div class="scroll"><table><tr><th>Gate</th><th>Name</th><th>Progress</th>'
             "<th>Done</th><th>Failing</th><th>Veto holder</th></tr>")
    for gid, gname, gpurpose, gveto in GATES:
        grows = [r for r in app if r["gate"] == gid]
        if not grows:
            continue
        done = len([r for r in grows if r["status"] in ("pass", "na", "waived")])
        failing = len([r for r in grows if r["status"] == "fail"])
        pct = int(100 * done / len(grows))
        H.append("<tr><td><code>%s</code></td><td>%s</td>"
                 "<td><div class='bar%s'><i style='width:%d%%'></i></div></td>"
                 "<td>%d/%d</td><td>%s</td><td>%s</td></tr>"
                 % (gid, _esc(gname), " has-fail" if failing else "", pct,
                    done, len(grows),
                    ("<span class='pill p-fail'>%d</span>" % failing) if failing else "0",
                    _esc(gveto)))
    H.append("</table></div>")

    for gid, gname, gpurpose, gveto in GATES:
        grows = [r for r in rows if r["gate"] == gid]
        if not any(r["applicable"] for r in grows):
            continue
        H.append('<div class="gatehead"><h2>%s &mdash; %s</h2></div>' % (gid, _esc(gname)))
        H.append('<div class="sub">%s &middot; veto holder: <strong>%s</strong></div>'
                 % (_esc(gpurpose), _esc(gveto)))
        H.append('<div class="scroll"><table><tr><th>ID</th><th>Sev</th><th>Status</th>'
                 "<th>Proof</th><th>Check &amp; evidence</th></tr>")
        for row in grows:
            if not row["applicable"] and row["status"] == "na" and not row["records"]:
                continue
            pill = {"pass": "p-pass", "fail": "p-fail", "todo": "p-todo",
                    "na": "p-na", "waived": "p-waived"}[row["status"]]
            H.append("<tr><td><code>%s</code></td>"
                     "<td><span class='sev s-%s'>%s</span></td>"
                     "<td><span class='pill %s'>%s</span></td>"
                     "<td><span class='proof pr-%s'>%s</span></td>"
                     "<td><strong>%s</strong>%s</td></tr>"
                     % (row["id"], row["sev"], row["sev"], pill, row["status"].upper(),
                        row["proof"], row["proof"], _esc(row["title"]),
                        render_records(row)))
        H.append("</table></div>")

    H.append("<h2>Evidence integrity</h2>")
    if integrity_bad or integrity_missing:
        H.append('<div class="note" style="border-color:var(--fail)"><strong>'
                 "Evidence has changed since it was recorded.</strong> "
                 "%d file(s) do not match their hash; %d are missing. "
                 "Treat this whole report as untrustworthy until explained.</div>"
                 % (len(integrity_bad), len(integrity_missing)))
        for rel in integrity_bad + integrity_missing:
            H.append('<div class="meta">%s</div>' % _esc(rel))
    else:
        H.append('<div class="note"><strong>%d evidence file(s) verified.</strong> '
                 "Every log and attachment matches the SHA-256 recorded at the moment it was "
                 "captured. Re-check at any time with <code>python lrk.py verify</code>.</div>"
                 % integrity_ok)

    H.append('<div class="foot">Launch Readiness Kit &middot; %d checks in catalogue, %d applicable '
             "to this profile. This report is generated from recorded evidence; it has no opinions "
             "and cannot be argued with. Raw logs live in <code>%s</code>."
             "</div>" % (len(CATALOG), len(app),
                         _esc(os.path.join(DIRNAME, "evidence"))))
    H.append("</div>")

    os.makedirs(kit.report_dir, exist_ok=True)
    out_path = os.path.join(kit.report_dir, "LAUNCH-REPORT.html")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(H))
    man_path, man_count = _write_manifest(kit)

    kit.audit("report", {"verdict": verdict, "path": out_path})
    kit.save()

    size = os.path.getsize(out_path)
    banner = {"GO": green, "GO WITH CONDITIONS": yellow, "NO-GO": red}[verdict]
    print(banner(bold("VERDICT: %s" % verdict)))
    print("  report   : %s  (%s)" % (out_path, human_bytes(size)))
    print("  manifest : %s  (%d files hashed)" % (man_path, man_count))
    print(dim("  open the report in a browser -- it is fully self-contained."))


def cmd_bundle(args):
    kit = Kit(find_root(args.root))
    kit.load()
    cmd_report(args)
    name = "launch-evidence-%s-%s.zip" % (slugify(kit.state["project"]["name"]), today())
    out = os.path.abspath(args.out or os.path.join(kit.root, name))
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _d, files in os.walk(kit.dir):
            for f in files:
                p = os.path.join(dirpath, f)
                z.write(p, os.path.join("launch-evidence", os.path.relpath(p, kit.dir)))
                count += 1
    print(green("BUNDLED") + "  %s" % out)
    print("  %d file(s), %s" % (count, human_bytes(os.path.getsize(out))))
    print(dim("  this zip is the thing you hand to a reviewer, an auditor, or a customer."))


def cmd_selftest(args):
    """Prove the kit itself works. Runs a full cycle in a temp directory."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="lrk-selftest-")
    failures = []

    def step(label, fn):
        try:
            fn()
            print(green("  ok   ") + label)
        except Exception as exc:
            failures.append((label, exc))
            print(red("  FAIL ") + "%s -- %s" % (label, exc))

    print(bold("lrk self-test in %s" % tmp))
    me = os.path.abspath(__file__)
    py = sys.executable.replace("\\", "/")

    def sh(*a):
        r = subprocess.run([sys.executable, me] + list(a), cwd=tmp,
                           capture_output=True, timeout=180)
        return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")

    def s_init():
        rc, o = sh("init", "--name", "SelfTest", "--profile", "api,db")
        assert rc == 0, o
        assert os.path.isfile(os.path.join(tmp, DIRNAME, "state.json")), "no state.json"

    def s_pass():
        rc, o = sh("run", "G1.01", "--", "%s -c \"print('build ok')\"" % py)
        assert rc == 0, o
        assert "PASS" in o, o

    def s_fail():
        rc, o = sh("run", "G1.03", "--", "%s -c \"raise SystemExit(3)\"" % py)
        assert rc == 1, "a failing command must exit 1, got %d\n%s" % (rc, o)
        assert "FAIL" in o, o

    def s_unicode_output_survives():
        # Regression: echoing a tool's Unicode output crashed on a cp1252 console,
        # losing the run. Evidence must never be destroyed by a console encoding.
        # Write raw UTF-8 bytes so the child's own console encoding is not the
        # variable under test -- what matters is that lrk can decode them and
        # echo them without dying.
        rc, o = sh("run", "G1.05", "--", py, "-c",
                   "import sys; sys.stdout.buffer.write("
                   "'\\u2139 \\u2713 caf\\u00e9 \\u2014 \\u4f60\\u597d'.encode('utf-8'))")
        assert rc == 0, "unicode in command output broke the run\n%s" % o
        assert "PASS" in o, o
        assert "UnicodeEncodeError" not in o, "lrk itself crashed on unicode\n%s" % o

    def s_expect_fail():
        rc, o = sh("run", "G2.06", "--expect-fail", "--",
                   "%s -c \"raise SystemExit(1)\"" % py)
        assert rc == 0, "expect-fail should treat non-zero as PASS\n%s" % o

    def s_quoting_preserved():
        # Regression: argv rejoin used to drop the caller's quotes, so a regex
        # containing | and () was handed to the shell as syntax.
        rc, o = sh("run", "G1.06", "--title", "quoting", "--expect-empty", "--",
                   py, "-c", "import sys; sys.stdout.write('')  # a|b(c)")
        assert rc == 0, "quoted argument containing shell metacharacters broke\n%s" % o

    def s_expect_empty_pass():
        rc, o = sh("run", "G1.11", "--expect-empty", "--",
                   "%s -c \"pass\"" % py)
        assert rc == 0 and "PASS" in o, o

    def s_expect_empty_catches_hits():
        # Regression: grep exits 0 when it FINDS something. Under the plain
        # exit-code rule a secret-scan hit would have been recorded as a pass.
        rc, o = sh("run", "G1.10", "--expect-empty", "--",
                   "%s -c \"print('sk_live_leakedkey')\"" % py)
        assert rc == 1, "a scan that FOUND something must FAIL, got rc=%d\n%s" % (rc, o)
        assert "found 1 line" in o, o

    def s_broken_scan_is_not_a_clean_scan():
        # Regression: a scan command that cannot run produces no stdout. That must
        # never be recorded as "found nothing" -- it is the difference between
        # "no secrets" and "the secret scanner is not installed".
        rc, o = sh("run", "G1.10", "--expect-empty", "--", "this-command-does-not-exist-xyz")
        assert rc == 1, "a scan that could not RUN must FAIL, got rc=%d\n%s" % (rc, o)
        assert "did not run correctly" in o, o

    def s_manual_needs_note():
        rc, o = sh("manual", "G0.09", "--status", "pass")
        assert rc != 0, "a manual pass without a note must be rejected\n%s" % o

    def s_manual_ok():
        rc, o = sh("manual", "G0.09", "--status", "pass", "--note", "three money paths listed")
        assert rc == 0, o

    def s_s0_waiver_guard():
        rc, o = sh("waive", "G1.10", "--by", "x", "--reason", "y", "--risk", "z")
        assert rc != 0, "S0 must refuse a waiver without --accept-blocker-risk\n%s" % o

    def s_report():
        rc, o = sh("report")
        p = os.path.join(tmp, DIRNAME, "report", "LAUNCH-REPORT.html")
        assert os.path.isfile(p), "no report written\n%s" % o
        body = open(p, "r", encoding="utf-8").read()
        assert "Launch Readiness Report" in body
        assert "NO-GO" in body, "an incomplete project must not report GO"

    def s_verify_clean():
        rc, o = sh("verify")
        assert rc == 0, o

    def s_tamper_detected():
        logs = []
        for dp, _d, fs in os.walk(os.path.join(tmp, DIRNAME, "evidence")):
            for f in fs:
                logs.append(os.path.join(dp, f))
        assert logs, "no evidence to tamper with"
        with open(logs[0], "a", encoding="utf-8") as fh:
            fh.write("\nEVERYTHING IS FINE, TRUST ME\n")
        rc, o = sh("verify")
        assert rc != 0 and "TAMPERED" in o, "tampering was not detected!\n%s" % o

    def s_certify_nogo():
        rc, o = sh("certify")
        assert rc == 1 and "NO-GO" in o, o
        assert os.path.isfile(os.path.join(tmp, DIRNAME, "CERTIFICATE.md"))

    cases = (
        ("init creates state", s_init),
        ("run records a passing command", s_pass),
        ("run records a failing command and exits 1", s_fail),
        ("unicode in tool output does not destroy the run", s_unicode_output_survives),
        ("--expect-fail inverts the verdict (sabotage tests)", s_expect_fail),
        ("shell metacharacters in a quoted argument survive", s_quoting_preserved),
        ("--expect-empty passes when a scan finds nothing", s_expect_empty_pass),
        ("--expect-empty FAILS when a scan finds something", s_expect_empty_catches_hits),
        ("a scan that cannot RUN is not a clean scan", s_broken_scan_is_not_a_clean_scan),
        ("manual pass without a note is refused", s_manual_needs_note),
        ("manual pass with a note is accepted", s_manual_ok),
        ("S0 waiver refused without explicit risk acceptance", s_s0_waiver_guard),
        ("report generates and says NO-GO while incomplete", s_report),
        ("verify passes on untouched evidence", s_verify_clean),
        ("verify DETECTS tampered evidence", s_tamper_detected),
        ("certify writes a NO-GO certificate and exits 1", s_certify_nogo),
    )
    total = len(cases)
    for label, fn in cases:
        step(label, fn)

    print()
    if failures:
        print(red(bold("SELF-TEST FAILED: %d of %d" % (len(failures), total))))
        print(dim("temp dir kept for inspection: %s" % tmp))
        raise SystemExit(1)
    print(green(bold("SELF-TEST PASSED: %d/%d" % (total, total))))
    shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="lrk.py",
        description="Launch Readiness Kit -- capture evidence, compute a verdict, "
                    "produce proof a human can read.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python lrk.py init --name "Acme API" --profile api,db,auth,cloud --version 1.0.0
  python lrk.py run G1.03 -- npm run typecheck
  python lrk.py run G2.06 --expect-fail --title "sabotage: break price calc" -- npm test
  python lrk.py manual G0.09 --status pass --note "money paths: signup, checkout, refund"
  python lrk.py attach G8.13 ./friction-log.md --caption "Customer Zero, 41 min"
  python lrk.py waive G6.12 --by "R. Patel" --reason "pre-revenue" --risk "cost surprise at 10x"
  python lrk.py status --verbose
  python lrk.py report && python lrk.py certify && python lrk.py bundle
""")
    p.add_argument("--root", help="project root (defaults to the nearest parent containing .launch)")
    sub = p.add_subparsers(dest="cmd")

    q = sub.add_parser("init", help="initialise the kit in this project")
    q.add_argument("--name")
    q.add_argument("--version", default="")
    q.add_argument("--owner", default="")
    q.add_argument("--profile", help="comma-separated tags, e.g. web,api,db,auth,pii,cloud")
    q.add_argument("--force", action="store_true")

    sub.add_parser("detect", help="report detected stack and suggested commands")

    q = sub.add_parser("profile", help="show or change the applicability profile")
    q.add_argument("--set")

    q = sub.add_parser("run", help="run a command and record it as evidence")
    q.add_argument("check_id")
    q.add_argument("--title", default="")
    q.add_argument("--note", default="")
    q.add_argument("--cwd")
    q.add_argument("--timeout", type=int, default=3600)
    q.add_argument("--tail", type=int, default=12, help="lines of output to echo (0 = none)")
    q.add_argument("--expect-fail", action="store_true",
                   help="a NON-ZERO exit means PASS (sabotage and negative tests)")
    q.add_argument("--expect-empty", action="store_true",
                   help="NO OUTPUT means PASS. Use for every scan check (grep for secrets, "
                        "debug code, localhost URLs) -- grep exits 0 when it FINDS something, "
                        "so the plain exit-code rule would record a hit as a pass.")
    q.add_argument("--shell", choices=["auto", "bash", "cmd"], default="auto",
                   help="which shell interprets the command. On Windows, 'bash' routes POSIX "
                        "one-liners through Git Bash instead of cmd.exe.")
    q.add_argument("--record-only", action="store_true",
                   help="capture output without changing the check's status")

    q = sub.add_parser("manual", help="record a human/observed result")
    q.add_argument("check_id")
    q.add_argument("--status", required=True, choices=["pass", "fail", "na", "todo"])
    q.add_argument("--note", default="")
    q.add_argument("--by", default="")
    q.add_argument("--attach")
    q.add_argument("--caption", default="")

    q = sub.add_parser("attach", help="attach a proof file to a check")
    q.add_argument("check_id")
    q.add_argument("file")
    q.add_argument("--caption", default="")

    q = sub.add_parser("waive", help="record a written waiver")
    q.add_argument("check_id")
    q.add_argument("--by", required=False)
    q.add_argument("--reason", required=False)
    q.add_argument("--risk", required=False)
    q.add_argument("--expires", default="")
    q.add_argument("--accept-blocker-risk", action="store_true")

    q = sub.add_parser("status", help="one-screen progress and verdict")
    q.add_argument("--gate")
    q.add_argument("--verbose", action="store_true")

    q = sub.add_parser("checklist", help="list checks and their state")
    q.add_argument("--gate")
    q.add_argument("--todo", action="store_true", help="only unfinished or failing checks")
    q.add_argument("--md", action="store_true", help="emit markdown")

    sub.add_parser("verify", help="re-hash every evidence file and detect tampering")
    sub.add_parser("report", help="build the self-contained HTML report")
    sub.add_parser("certify", help="write CERTIFICATE.md with the GO/NO-GO verdict")

    q = sub.add_parser("bundle", help="report + zip the whole evidence directory")
    q.add_argument("--out")

    sub.add_parser("selftest", help="prove the kit itself works (11 assertions)")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    raw_command = None
    if "--" in argv:
        i = argv.index("--")
        raw_command = argv[i + 1:]          # keep as a list; cmd_run re-quotes it
        argv = argv[:i]

    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0

    dispatch = {
        "init": cmd_init, "detect": cmd_detect, "profile": cmd_profile,
        "manual": cmd_manual, "attach": cmd_attach, "waive": cmd_waive,
        "status": cmd_status, "checklist": cmd_checklist, "verify": cmd_verify,
        "report": cmd_report, "certify": cmd_certify, "bundle": cmd_bundle,
        "selftest": cmd_selftest,
    }
    if args.cmd == "run":
        return cmd_run(args, raw_command)
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except KeyboardInterrupt:
        sys.stderr.write("\ninterrupted\n")
        raise SystemExit(130)
