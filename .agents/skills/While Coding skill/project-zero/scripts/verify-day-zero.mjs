#!/usr/bin/env node
/**
 * PROJECT ZERO — THE DAY-ZERO GATE
 *
 * Zero dependencies. Node 18+.
 *
 *   node verify-day-zero.mjs [dir]     check the seven criteria (default: .)
 *   node verify-day-zero.mjs --json    machine-readable output
 *   node verify-day-zero.mjs --self-test
 *
 * EXIT CODES
 *   0  every automatable criterion passes (manual ones still need evidence)
 *   1  at least one criterion fails
 *   2  bad usage / unreadable input
 *
 * WHAT THIS IS
 * founder-mode/references/08-bootstrap.md defines the bar a greenfield repo
 * must clear before slice 1 starts. That bar is seven items. This program
 * checks them so that "are we ready to build features?" is answered by an exit
 * code instead of by whoever is most optimistic in the room.
 *
 * WHAT IT DELIBERATELY CANNOT CHECK
 * Three of the seven require a human to have WATCHED something happen:
 *   - a test you saw fail before it passed
 *   - a migration rollback you executed
 *   - a deploy rollback you executed
 * A file's existence proves none of those. Those report MANUAL and are recorded
 * in .project-zero.json only when a human passes --attest, so that the claim has
 * a name and a date attached to it rather than being assumed by a script.
 *
 * WHY DETECTION IS SIGNAL-BASED, NOT NAME-BASED
 * Projects differ. This looks for the SIGNAL (is there a lockfile? does any CI
 * config run the test command?) rather than for one blessed filename, so it
 * works on a stack it has never seen. Where it cannot tell, it says UNKNOWN
 * rather than guessing — a false OK here is worse than no check at all.
 */

import { readFileSync, readdirSync, statSync, existsSync, writeFileSync } from "node:fs";
import { join, resolve, basename } from "node:path";

/* ------------------------------------------------------------------ helpers */

const SKIP_DIR = new Set([
  "node_modules", ".git", "dist", "build", ".next", ".nuxt", ".svelte-kit",
  "out", "coverage", "vendor", ".turbo", ".cache", "target", "__pycache__",
  ".venv", "venv", ".gradle", "bin", "obj",
]);

/** Walk the tree once. Everything below reads from this snapshot. */
function walk(root, acc = { files: [], dirs: [] }, depth = 0) {
  if (depth > 6) return acc;
  let entries;
  try { entries = readdirSync(root); } catch { return acc; }
  for (const e of entries) {
    const p = join(root, e);
    let st;
    try { st = statSync(p); } catch { continue; }
    if (st.isDirectory()) {
      if (SKIP_DIR.has(e)) continue;
      acc.dirs.push(p);
      walk(p, acc, depth + 1);
    } else {
      acc.files.push(p);
    }
  }
  return acc;
}

const read = (p) => { try { return readFileSync(p, "utf8"); } catch { return ""; } };
const hasFile = (tree, re) => tree.files.some((f) => re.test(basename(f)));
const findFile = (tree, re) => tree.files.find((f) => re.test(basename(f)));
/** Search file CONTENTS, restricted to files whose name matches `nameRe`. */
const anyContent = (tree, nameRe, contentRe) =>
  tree.files.some((f) => nameRe.test(basename(f)) && contentRe.test(read(f)));

/* -------------------------------------------------------------- stack sniff */

const MANIFESTS = [
  [/^package\.json$/, "node"],
  [/^pyproject\.toml$|^requirements\.txt$/, "python"],
  [/^go\.mod$/, "go"],
  [/^Cargo\.toml$/, "rust"],
  [/^pom\.xml$|^build\.gradle(\.kts)?$/, "jvm"],
  [/^Gemfile$/, "ruby"],
  [/^composer\.json$/, "php"],
  [/\.csproj$|\.sln$/, "dotnet"],
];

const LOCKFILES = /^(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb|poetry\.lock|uv\.lock|Pipfile\.lock|go\.sum|Cargo\.lock|Gemfile\.lock|composer\.lock|packages\.lock\.json)$/;

function detectStack(tree) {
  const found = new Set();
  for (const f of tree.files) {
    for (const [re, name] of MANIFESTS) if (re.test(basename(f))) found.add(name);
  }
  return [...found];
}

/* ----------------------------------------------------------------- criteria */

/**
 * Each criterion returns { status, detail, fix }.
 *   OK      — proven by a signal in the repo
 *   FAIL    — the signal is absent
 *   MANUAL  — cannot be proven by inspection; needs attested human evidence
 *   UNKNOWN — the stack is unrecognized, so absence is not evidence of absence
 */
const CRITERIA = [
  {
    id: "static-analysis",
    title: "Typecheck / lint / format configured",
    law: "Law 6",
    check(tree, stack) {
      const signals = [
        hasFile(tree, /^tsconfig(\..*)?\.json$/),
        hasFile(tree, /^\.eslintrc|^eslint\.config\./),
        hasFile(tree, /^biome\.json(c)?$/),
        hasFile(tree, /^\.prettierrc|^prettier\.config\./),
        hasFile(tree, /^ruff\.toml$|^\.flake8$|^mypy\.ini$/),
        hasFile(tree, /^\.golangci\.ya?ml$/),
        hasFile(tree, /^rustfmt\.toml$|^clippy\.toml$/),
        hasFile(tree, /^\.editorconfig$/),
        anyContent(tree, /^pyproject\.toml$/, /\[tool\.(ruff|mypy|black)\]/),
        anyContent(tree, /^package\.json$/, /"(lint|typecheck|format)"\s*:/),
      ].filter(Boolean).length;

      if (signals === 0) {
        return {
          status: stack.length ? "FAIL" : "UNKNOWN",
          detail: stack.length ? "no linter, formatter, or typechecker config found" : "no recognized manifest — cannot tell",
          fix: "Add a typechecker, a linter, and a formatter, and wire them to commands CI can run.",
        };
      }
      return { status: "OK", detail: `${signals} config signal(s)` };
    },
  },
  {
    id: "test-runner",
    title: "Test runner present, with a real test",
    law: "Law 2 / founder-mode R1",
    check(tree, stack) {
      const testFiles = tree.files.filter((f) =>
        /(\.|_)(test|spec)\.[a-z]+$/.test(basename(f)) ||
        /^test_.*\.py$/.test(basename(f)) ||
        /_test\.go$/.test(basename(f)),
      );
      const runner =
        anyContent(tree, /^package\.json$/, /"(test)"\s*:/) ||
        hasFile(tree, /^(jest|vitest|playwright|cypress)\.config\./) ||
        hasFile(tree, /^pytest\.ini$|^tox\.ini$/) ||
        anyContent(tree, /^pyproject\.toml$/, /\[tool\.pytest/) ||
        stack.includes("go") || stack.includes("rust");

      if (!runner && testFiles.length === 0) {
        return {
          status: stack.length ? "FAIL" : "UNKNOWN",
          detail: "no test runner and no test files",
          fix: "Install a test runner and write one real test. Then break it on purpose and watch it fail.",
        };
      }
      if (testFiles.length === 0) {
        return { status: "FAIL", detail: "runner configured but zero test files", fix: "Write one real test." };
      }
      return { status: "OK", detail: `${testFiles.length} test file(s)` };
    },
  },
  {
    id: "test-watched-failing",
    title: "A test you watched FAIL, then pass",
    law: "Law 2",
    manual: true,
    fix: "Break the assertion, run the suite, see it red, restore it, see it green. Paste both outputs.",
  },
  {
    id: "migration-rollback",
    title: "Migration tool with a rollback you executed",
    law: "Law 7",
    manual: true,
    check(tree) {
      // Presence is necessary but not sufficient — it never proves execution.
      const dir = tree.dirs.find((d) => /(^|[\\/])(migrations|migrate|alembic|prisma)$/i.test(d));
      const tool =
        hasFile(tree, /^schema\.prisma$/) ||
        hasFile(tree, /^alembic\.ini$/) ||
        anyContent(tree, /^package\.json$/, /"(migrate|db:migrate)"/) ||
        !!dir;
      return tool
        ? { status: "MANUAL", detail: "tool present — execution still unproven" }
        : { status: "MANUAL", detail: "no migration tool found (fine if the project has no database)" };
    },
    fix: "Run the migration up, then down, on a real database. Paste both outputs.",
  },
  {
    id: "ci",
    title: "CI runs the full set on every push",
    law: "Law 6",
    check(tree) {
      const ciFiles = tree.files.filter((f) =>
        /[\\/]\.github[\\/]workflows[\\/].*\.ya?ml$/.test(f) ||
        /^\.gitlab-ci\.ya?ml$|^Jenkinsfile$|^azure-pipelines\.ya?ml$|^\.circleci$/.test(basename(f)),
      );
      if (ciFiles.length === 0) {
        return { status: "FAIL", detail: "no CI configuration found", fix: "Add a pipeline that runs typecheck, lint, test, and build on every push." };
      }
      // A pipeline that does not run the tests is theatre.
      const body = ciFiles.map(read).join("\n");
      const runsTests = /\btest\b/i.test(body);
      const onPush = /\bon:|push|pull_request|trigger/i.test(body);
      if (!runsTests) {
        return { status: "FAIL", detail: `${ciFiles.length} CI file(s) but none reference a test step`, fix: "Make CI run the test command." };
      }
      return { status: "OK", detail: `${ciFiles.length} CI file(s)${onPush ? ", triggered on push" : ""}` };
    },
  },
  {
    id: "deploy-rollback",
    title: "A deploy, and a rollback you executed",
    law: "Law 7",
    manual: true,
    fix: "Deploy, then roll back to the previous version. Time it. Paste both outputs.",
  },
  {
    id: "config-contract",
    title: "Config contract: .env.example + boot-time validation",
    law: "Law 3",
    check(tree, stack) {
      const example = findFile(tree, /^\.env\.example$|^\.env\.sample$|^\.env\.template$/);
      // The validation signal: something parses/asserts the environment in one place.
      const validated =
        anyContent(tree, /^(config|env|settings)\.[jt]s$/, /z\.object|envalid|joi|superstruct|valibot|throw new|process\.exit/) ||
        anyContent(tree, /^(config|settings)\.py$/, /BaseSettings|pydantic|os\.environ\[/) ||
        anyContent(tree, /\.[jt]s$/, /required environment|missing environment|Missing required env/i);

      if (!example && !validated) {
        return {
          status: stack.length ? "FAIL" : "UNKNOWN",
          detail: "no .env.example and no startup validation",
          fix: "Declare every variable in one schema, parse it at boot, and refuse to start when it is wrong.",
        };
      }
      if (!example) return { status: "FAIL", detail: "validation present but no .env.example", fix: "Commit a complete .env.example." };
      if (!validated) return { status: "FAIL", detail: ".env.example present but nothing validates at startup", fix: "Parse and validate config once at boot; exit non-zero when invalid." };

      // A committed real .env is a secret leak, and it is worth failing loudly for.
      if (hasFile(tree, /^\.env$/)) {
        return { status: "FAIL", detail: "a real .env is committed — rotate those secrets", fix: "Delete .env from the repo, add it to .gitignore, and rotate every value in it." };
      }
      return { status: "OK", detail: `${basename(example)} + startup validation` };
    },
  },
  {
    id: "observability",
    title: "One health endpoint and one metric",
    law: "Law 8",
    check(tree) {
      const health = tree.files.some((f) => /health|readyz|livez|healthz/i.test(basename(f))) ||
        anyContent(tree, /\.[jtpg][sytmo]/, /\/health|healthz|readyz|livez/);
      const logging = anyContent(tree, /(logger|logging)\.[a-z]+$/, /./) ||
        anyContent(tree, /\.[jt]s$/, /pino|winston|bunyan|structlog|zerolog|slog\./);
      if (!health && !logging) {
        return { status: "FAIL", detail: "no health endpoint and no structured logger", fix: "Add /health that checks dependencies, and a structured logger with correlation ids." };
      }
      if (!health) return { status: "FAIL", detail: "structured logging present, no health endpoint", fix: "Add /health that actually checks its dependencies." };
      if (!logging) return { status: "FAIL", detail: "health endpoint present, no structured logger", fix: "Add structured JSON logging with a correlation id." };
      return { status: "OK", detail: "health endpoint + structured logging" };
    },
  },
  {
    id: "pinned",
    title: "Versions pinned, lockfile committed",
    law: "Law 1",
    check(tree, stack) {
      const lock = findFile(tree, LOCKFILES);
      const runtimePin =
        hasFile(tree, /^\.nvmrc$|^\.tool-versions$|^\.python-version$|^rust-toolchain(\.toml)?$/) ||
        anyContent(tree, /^package\.json$/, /"engines"\s*:/) ||
        anyContent(tree, /^go\.mod$/, /^go \d/m) ||
        anyContent(tree, /^pyproject\.toml$/, /requires-python/);
      if (!lock && !stack.length) return { status: "UNKNOWN", detail: "no recognized manifest" };
      if (!lock) return { status: "FAIL", detail: "no lockfile committed", fix: "Commit the lockfile. Without it, two machines build two different programs." };
      if (!runtimePin) return { status: "FAIL", detail: `${basename(lock)} present, but the runtime version is unpinned`, fix: "Pin the language runtime (.nvmrc, .tool-versions, engines, requires-python…)." };
      return { status: "OK", detail: `${basename(lock)} + pinned runtime` };
    },
  },
];

/* ------------------------------------------------------------- attestations */

const ATTEST_FILE = ".project-zero.json";

function loadAttestations(root) {
  const p = join(root, ATTEST_FILE);
  if (!existsSync(p)) return {};
  try { return JSON.parse(read(p)).attested ?? {}; } catch { return {}; }
}

function saveAttestation(root, id, who) {
  const p = join(root, ATTEST_FILE);
  let data = { attested: {} };
  if (existsSync(p)) { try { data = JSON.parse(read(p)); } catch { /* overwrite corrupt */ } }
  data.attested = data.attested ?? {};
  data.attested[id] = { by: who, at: new Date().toISOString() };
  writeFileSync(p, JSON.stringify(data, null, 2) + "\n");
  return data.attested[id];
}

/* ---------------------------------------------------------------- reporting */

const ICON = { OK: "OK  ", FAIL: "FAIL", MANUAL: "TODO", UNKNOWN: "??  " };

function run(root, { json = false } = {}) {
  const tree = walk(resolve(root));
  const stack = detectStack(tree);
  const attested = loadAttestations(resolve(root));

  const results = CRITERIA.map((c) => {
    let r = c.check ? c.check(tree, stack) : {};
    let status = r.status ?? (c.manual ? "MANUAL" : "UNKNOWN");
    let detail = r.detail ?? "";

    // A human attestation upgrades MANUAL to OK, and records who said so.
    if (status === "MANUAL" && attested[c.id]) {
      status = "OK";
      detail = `attested by ${attested[c.id].by} on ${attested[c.id].at.slice(0, 10)}`;
    }
    return { id: c.id, title: c.title, law: c.law, status, detail, fix: r.fix ?? c.fix };
  });

  if (json) {
    console.log(JSON.stringify({ stack, results }, null, 2));
    return results.some((r) => r.status === "FAIL") ? 1 : 0;
  }

  console.log(`\nproject-zero — day-zero gate`);
  console.log(`repo:  ${resolve(root)}`);
  console.log(`stack: ${stack.length ? stack.join(", ") : "not detected"}`);
  console.log("-".repeat(78));

  for (const r of results) {
    console.log(`  ${ICON[r.status]}  ${r.title}`);
    if (r.detail) console.log(`        ${r.detail}`);
  }

  const failed = results.filter((r) => r.status === "FAIL");
  const manual = results.filter((r) => r.status === "MANUAL");
  const unknown = results.filter((r) => r.status === "UNKNOWN");

  if (failed.length || manual.length) {
    console.log(`\n${"-".repeat(78)}\nWhat is left:\n`);
    for (const r of [...failed, ...manual]) {
      console.log(`  ${r.title}`);
      if (r.fix) console.log(`    → ${r.fix}`);
    }
  }

  console.log(`\n${"=".repeat(78)}`);
  if (failed.length === 0 && manual.length === 0) {
    console.log("Day zero complete. Slice 1 may start.");
    if (unknown.length) console.log(`(${unknown.length} criterion/criteria unknown — verify by hand.)`);
    return 0;
  }
  console.log(
    `${failed.length} failing, ${manual.length} awaiting human evidence.\n` +
    `Slice 1 does not start until these are real. Attest a manual one with:\n` +
    `  node verify-day-zero.mjs --attest <id> --by "<name>"`,
  );
  return failed.length ? 1 : 1;
}

/* ---------------------------------------------------------------- self-test */

function selfTest() {
  const problems = [];
  const ids = CRITERIA.map((c) => c.id);
  if (new Set(ids).size !== ids.length) problems.push("duplicate criterion id");
  if (CRITERIA.length !== 9) problems.push(`expected 9 criteria, found ${CRITERIA.length}`);
  for (const c of CRITERIA) {
    if (!c.title || !c.id) problems.push(`criterion missing id/title: ${JSON.stringify(c)}`);
    if (!c.check && !c.manual) problems.push(`${c.id}: neither checkable nor manual`);
    if (c.check) {
      // Every checker must survive an empty repo without throwing.
      const r = c.check({ files: [], dirs: [] }, []);
      if (!r || !r.status) problems.push(`${c.id}: checker returned no status on an empty tree`);
    }
  }
  if (problems.length) {
    console.error("FAIL: day-zero verifier self-test\n  " + problems.join("\n  "));
    return 1;
  }
  console.log("PASS: day-zero verifier self-test");
  return 0;
}

/* -------------------------------------------------------------------- main */

function main() {
  const argv = process.argv.slice(2);

  if (argv.includes("--help") || argv.includes("-h")) {
    console.log(`
project-zero — the day-zero gate

  node verify-day-zero.mjs [dir]                 check the criteria (default: .)
  node verify-day-zero.mjs --json               machine-readable
  node verify-day-zero.mjs --attest <id> --by "<name>"
  node verify-day-zero.mjs --self-test

Criteria: ${CRITERIA.map((c) => c.id).join(", ")}

Three criteria cannot be proven by inspecting files — they require a human to
have watched something happen. Those stay TODO until attested by name.
`);
    return 0;
  }

  if (argv.includes("--self-test")) return selfTest();

  const ai = argv.indexOf("--attest");
  if (ai !== -1) {
    const id = argv[ai + 1];
    const bi = argv.indexOf("--by");
    const who = bi !== -1 ? argv[bi + 1] : "";
    if (!id || !CRITERIA.some((c) => c.id === id)) {
      console.error(`--attest needs a valid criterion id. One of:\n  ${CRITERIA.map((c) => c.id).join("\n  ")}`);
      return 2;
    }
    if (!who) { console.error('--attest requires --by "<name>". An unsigned attestation is not evidence.'); return 2; }
    const rec = saveAttestation(resolve("."), id, who);
    console.log(`Attested ${id} by ${rec.by} at ${rec.at}`);
    console.log(`Recorded in ${ATTEST_FILE} — commit it, it is project evidence.`);
    return 0;
  }

  const dir = argv.find((a) => !a.startsWith("--")) ?? ".";
  return run(dir, { json: argv.includes("--json") });
}

process.exit(main());
