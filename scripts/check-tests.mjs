#!/usr/bin/env node
/**
 * TEST CRAFT — THE TEST CHECKER
 *
 * Zero dependencies. Node 18+.
 *
 *   node check-tests.mjs [paths...]   check test files (default: .)
 *   node check-tests.mjs --json       machine-readable
 *   node check-tests.mjs --langs      list recognized languages
 *   node check-tests.mjs --self-test
 *
 * EXIT CODES
 *   0  clean
 *   1  findings
 *   2  bad usage
 *
 * ESCAPE HATCH, on the offending line or the line above it:
 *   test-allow: <rule-id> — <reason>
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THESE RULES
 *
 * Each one is a defect that makes a suite silently stop protecting you, and
 * each is mechanically decidable in any language:
 *
 *   focused-test      a committed `.only` disables every other test in the file
 *                     while CI stays green. Highest severity, lowest visibility.
 *   skipped-test      a permanently skipped test is a lie about coverage
 *   no-assertion      a test that asserts nothing proves only "it did not throw"
 *   sleep-in-test     a slept race is still a race, and now it is also slow
 *   loop-in-test      a loop can run zero times and assert nothing
 *   empty-test        a placeholder that counts as a passing test
 *
 * It does NOT judge whether an assertion is meaningful, whether a double should
 * have been a fake, or whether the test would catch the bug. Those need
 * judgment; a checker that fakes judgment produces confident wrong answers.
 *
 * ON UNKNOWN LANGUAGES
 * Unrecognized extensions are skipped and counted, never guessed at.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, extname, basename, relative, resolve } from "node:path";

/* ------------------------------------------------------------------ config */

const DEFAULTS = {
  // A test file this long is a module's worth of tests in one place.
  maxTestFileLines: 800,
  // Directories whose contents are treated as tests regardless of filename.
  testDirs: ["test", "tests", "spec", "specs", "__tests__", "e2e", "it"],
};

const SKIP_DIR = new Set([
  "node_modules", ".git", "dist", "build", ".next", ".nuxt", "out", "coverage",
  "vendor", ".turbo", ".cache", "target", "__pycache__", ".venv", "venv",
  "fixtures", "__snapshots__", "testdata", "golden",
  // See check-code.mjs: gitignored scratch holding stale repo copies. 15,924 of 15,971 test
  // findings came from here against 47 real ones.
  "tmp",
]);

/* ---------------------------------------------------------------- languages
 *
 * `assert` — patterns that count as making an assertion.
 * `focus`  — patterns that restrict the run to a subset (the dangerous one).
 * `skip`   — patterns that disable a test.
 * `sleep`  — patterns that block on wall-clock time.
 * `case`   — patterns that open a single test case.
 * ------------------------------------------------------------------------ */

const JS_LIKE = {
  name: "JavaScript/TypeScript",
  comment: ["//"],
  case: [/\b(it|test|bench)\s*(\.\w+)?\s*\(/, /\bit\s*\.\s*each/],
  focus: [/\b(describe|it|test|context|suite)\s*\.\s*only\s*\(/, /\bf(describe|it)\s*\(/],
  skip: [/\b(describe|it|test|context)\s*\.\s*skip\s*\(/, /\bx(describe|it|test)\s*\(/, /\.\s*todo\s*\(/],
  assert: [/\bexpect\s*\(/, /\bassert\b/, /\bshould\b/, /\.\s*to\s*\./, /\bchai\b/, /\bsinon\b.*\.(called|calledWith)/],
  sleep: [/setTimeout\s*\(\s*(?:resolve|done)/, /\bsleep\s*\(/, /waitFor\s*\(\s*\d+\s*\)/, /\.\s*wait\s*\(\s*\d+\s*\)/],
};

const LANGS = {
  ".js": JS_LIKE, ".mjs": JS_LIKE, ".cjs": JS_LIKE,
  ".jsx": JS_LIKE, ".ts": JS_LIKE, ".tsx": JS_LIKE,

  ".py": {
    name: "Python",
    comment: ["#"],
    case: [/^\s*(?:async\s+)?def\s+test_/],
    focus: [/@pytest\.mark\.focus/, /\.only\b/],
    skip: [/@pytest\.mark\.skip/, /@unittest\.skip/, /pytest\.skip\s*\(/],
    assert: [/^\s*assert\b/, /\bself\.assert\w+\s*\(/, /\bpytest\.raises\b/, /\bassert_\w+\s*\(/],
    sleep: [/\btime\.sleep\s*\(/, /\basyncio\.sleep\s*\(/],
  },

  ".go": {
    name: "Go",
    comment: ["//"],
    case: [/^\s*func\s+(Test|Benchmark|Fuzz)\w*\s*\(/],
    focus: [/\bFocus\w*\s*\(/],
    skip: [/\bt\.Skip\s*\(/, /\bt\.SkipNow\s*\(/],
    assert: [/\bt\.(Error|Errorf|Fatal|Fatalf)\b/, /\b(assert|require)\.\w+\s*\(/, /\bwant\b.*\bgot\b/],
    sleep: [/\btime\.Sleep\s*\(/],
  },

  ".rb": {
    name: "Ruby",
    comment: ["#"],
    case: [/^\s*(it|specify|example)\s+/, /^\s*def\s+test_/],
    focus: [/\b(fit|fdescribe|fcontext)\s+/, /\bfocus:\s*true/],
    skip: [/\b(xit|xdescribe|xcontext|pending|skip)\b/],
    assert: [/\bexpect\s*\(/, /\bassert\w*\b/, /\.\s*should\b/, /\brefute\w*\b/],
    sleep: [/\bsleep\s*[\s(]/],
  },

  ".java": {
    name: "Java",
    comment: ["//"],
    case: [/@Test\b/],
    focus: [],
    skip: [/@Disabled\b/, /@Ignore\b/],
    assert: [/\bassert\w*\s*\(/, /\bassertThat\s*\(/, /\bverify\s*\(/, /\bexpectThrows\b/],
    sleep: [/Thread\.sleep\s*\(/],
  },

  ".kt": {
    name: "Kotlin",
    comment: ["//"],
    case: [/@Test\b/],
    focus: [],
    skip: [/@Disabled\b/, /@Ignore\b/],
    assert: [/\bassert\w*\s*\(/, /\bverify\s*\(/, /\bshouldBe\b/],
    sleep: [/Thread\.sleep\s*\(/, /\bdelay\s*\(/],
  },

  ".cs": {
    name: "C#",
    comment: ["//"],
    case: [/\[(Test|Fact|Theory|TestMethod)\]/],
    focus: [],
    skip: [/\[Ignore/, /\(Skip\s*=/],
    assert: [/\bAssert\.\w+\s*\(/, /\bShould\w*\s*\(/, /\.\s*Verify\s*\(/],
    sleep: [/Thread\.Sleep\s*\(/, /Task\.Delay\s*\(/],
  },

  ".rs": {
    name: "Rust",
    comment: ["//"],
    case: [/#\[test\]/, /#\[tokio::test\]/],
    focus: [],
    skip: [/#\[ignore\]/],
    assert: [/\bassert(_eq|_ne)?!\s*\(/, /\bpanic!\s*\(/, /\.\s*unwrap\s*\(\s*\)/],
    sleep: [/thread::sleep\s*\(/, /tokio::time::sleep\s*\(/],
  },

  ".php": {
    name: "PHP",
    comment: ["//", "#"],
    case: [/\bfunction\s+test\w*\s*\(/, /@test\b/],
    focus: [],
    skip: [/\$this->markTestSkipped/, /@group\s+skip/],
    assert: [/\$this->assert\w+\s*\(/, /\bexpect\s*\(/],
    sleep: [/\bsleep\s*\(/, /\busleep\s*\(/],
  },
};

/** A file that holds tests. Name convention first, then directory. */
function isTestFile(path, cfg) {
  const b = basename(path);
  if (/(\.|_|-)(test|spec)\.[a-z]+$/i.test(b)) return true;
  if (/^test_.*\.py$/i.test(b)) return true;
  if (/_test\.(go|py|rb|dart)$/i.test(b)) return true;
  if (/Test(s)?\.(java|kt|cs)$/i.test(b)) return true;
  if (/^(Test|Spec).*\.(java|kt|cs)$/i.test(b)) return true;
  const parts = path.split(/[\\/]/);
  return parts.some((p) => cfg.testDirs.includes(p.toLowerCase()));
}

/* -------------------------------------------------------------------- util */

const read = (p) => { try { return readFileSync(p, "utf8"); } catch { return ""; } };

function loadConfig(root) {
  const p = join(root, ".test-craft.json");
  if (!existsSync(p)) return { ...DEFAULTS };
  try { return { ...DEFAULTS, ...JSON.parse(read(p)) }; }
  catch {
    process.stderr.write(`warning: ${p} is not valid JSON — using defaults\n`);
    return { ...DEFAULTS };
  }
}

function parseAllow(line) {
  const m = /test-allow:\s*([a-z0-9-]+?)\s+[\u2014\u2013-]\s+(.+?)\s*(?:\*\/|-->|$)/.exec(line);
  if (m) return { id: m[1], reason: m[2].trim() };
  const bare = /test-allow:\s*([a-z0-9-]+)/.exec(line);
  if (bare) return { id: bare[1], reason: "" };
  return null;
}

const isComment = (line, lang) => lang.comment.some((c) => line.trimStart().startsWith(c));
const anyMatch = (patterns, line) => patterns.some((p) => p.test(line));

/**
 * The body of one test case, from its opening line to whichever comes first:
 * the next case, or a dedent to at or below the opening indentation.
 * Approximate on purpose — precise parsing per language is not worth the
 * false-confidence it would buy.
 */
/* A dedented line that merely FINISHES the declaration does not end the body.
   Bare closers (`)`, `}`, `]`) were already allowed, but Python ends a multi-line signature
   with `) -> None:` and Go with `) error {`. Treating those as the end truncated the body to
   the parameter list, which asserts nothing, so EVERY multi-line signature reported a false
   no-assertion -- and worse, the real body was never scanned, hiding genuine loop-in-test and
   sleep-in-test findings. */
const DECL_TAIL = /^\s*[})\]]*\s*(?:->\s*[^:{]+)?\s*[:{]?\s*[;,]?\s*$/;

function caseBody(lines, start, lang) {
  const open = lines[start];
  const baseIndent = open.length - open.trimStart().length;
  const body = [];
  for (let j = start + 1; j < lines.length; j++) {
    const l = lines[j];
    if (!l.trim()) { body.push(l); continue; }
    const ind = l.length - l.trimStart().length;
    if (ind <= baseIndent && (anyMatch(lang.case, l) || DECL_TAIL.test(l) === false)) {
      if (anyMatch(lang.case, l)) break;
      if (ind <= baseIndent && body.length > 0) break;
    }
    body.push(l);
    if (body.length > 400) break; // pathological; stop rather than scan a file
  }
  return body;
}

/* ---------------------------------------------------------------- checking */

function checkFile(path, root, cfg) {
  const lang = LANGS[extname(path)];
  const rel = relative(root, path) || path;
  if (!lang) return { skipped: true, rel };

  const text = read(path);
  if (!text) return { skipped: true, rel };
  const lines = text.split(/\r?\n/);
  const out = [];

  const allowAt = (n, id) => {
    const here = parseAllow(lines[n - 1] ?? "");
    const above = parseAllow(lines[n - 2] ?? "");
    return (here && here.id === id) || (above && above.id === id);
  };
  const add = (line, rule, why) => {
    if (!allowAt(line, rule)) out.push({ file: rel, line, rule, why, lang: lang.name });
  };

  lines.forEach((raw, i) => {
    const n = i + 1;
    if (isComment(raw, lang)) {
      const a = parseAllow(raw);
      if (a && a.reason === "") {
        add(n, "unexplained-escape",
          "An escape with no stated reason is a violation someone hid. Write why after an em dash.");
      }
      return;
    }

    // The highest-severity rule: a committed focus silently disables the rest.
    if (anyMatch(lang.focus, raw)) {
      add(n, "focused-test",
        "A committed focus disables every other test in this file while CI stays green. Remove it.");
    }
    if (anyMatch(lang.skip, raw)) {
      add(n, "skipped-test",
        "A permanently skipped test is a lie about coverage. Fix it, or delete it and note the gap.");
    }
    if (anyMatch(lang.sleep, raw)) {
      add(n, "sleep-in-test",
        "Law 9: a slept race is still a race, and now it is also slow. Wait for a condition instead.");
    }
  });

  // Per-case checks.
  for (let i = 0; i < lines.length; i++) {
    if (isComment(lines[i], lang)) continue;
    if (!anyMatch(lang.case, lines[i])) continue;

    const body = caseBody(lines, i, lang);
    const code = body.filter((l) => l.trim() && !isComment(l, lang));
    const n = i + 1;

    if (code.length === 0) {
      add(n, "empty-test", "An empty test body counts as a passing test and proves nothing.");
      continue;
    }
    if (!code.some((l) => anyMatch(lang.assert, l))) {
      add(n, "no-assertion",
        "No assertion found. This proves only that the code did not throw — say that out loud and it stops sounding like a test.");
    }
    /* Law 3 — a LOOP in a test body can iterate zero times and assert nothing,
       and it is unambiguous in every language.

       `if` is deliberately NOT flagged. In Go the standard assertion IS a
       conditional (`if got != want { t.Errorf(...) }`), and in table-driven
       tests everywhere it is idiomatic. Telling those apart from
       `if (flag) { expect(...) }` requires knowing whether the condition
       references the result under test — beyond a line-based checker. A rule
       that fires on correct idiomatic code gets the whole tool switched off,
       so this one is left to the review checklist. */
    const loops = code.filter((l) => /^\s*(for|while|forEach\s*\()\b/.test(l));
    if (loops.length > 0) {
      add(n, "loop-in-test",
        "A loop in a test body can run zero times and assert nothing. Use parameterized or table-driven cases so each input is its own reported result.");
    }
  }

  if (lines.length > cfg.maxTestFileLines) {
    add(1, "huge-test-file",
      `${lines.length} lines (limit ${cfg.maxTestFileLines}). Split by behavior so a failure points at an area.`);
  }

  return { violations: out, rel, lang: lang.name };
}

/* ----------------------------------------------------------------- walking */

function collect(target, acc = []) {
  let st;
  try { st = statSync(target); } catch { return acc; }
  if (st.isDirectory()) {
    if (SKIP_DIR.has(basename(target))) return acc;
    for (const e of readdirSync(target)) collect(join(target, e), acc);
    return acc;
  }
  acc.push(target);
  return acc;
}

function run(targets, { json = false } = {}) {
  const root = process.cwd();
  const cfg = loadConfig(root);
  const files = collect(resolve(targets[0] ?? "."));
  for (const t of targets.slice(1)) collect(resolve(t), files);

  const tests = files.filter((f) => isTestFile(f, cfg));
  const all = [];
  const langCount = new Map();
  let checked = 0, skipped = 0;

  for (const f of tests) {
    const r = checkFile(f, root, cfg);
    if (r.skipped) { skipped++; continue; }
    checked++;
    langCount.set(r.lang, (langCount.get(r.lang) ?? 0) + 1);
    all.push(...r.violations);
  }

  if (json) {
    console.log(JSON.stringify({ testFiles: checked, skipped, violations: all }, null, 2));
    return all.length ? 1 : 0;
  }

  if (checked === 0) {
    console.log(`test-craft: UNKNOWN — no recognized test files found (${files.length} file(s) scanned).`);
    console.log(`            Recognized: ${[...new Set(Object.values(LANGS).map((l) => l.name))].join(", ")}`);
    console.log(`            Test files are matched by name (*.test.*, *_test.*, test_*.py, *Test.java)`);
    console.log(`            or by living in ${cfg.testDirs.join("/")}.`);
    return 0;
  }

  if (all.length === 0) {
    const langs = [...langCount.entries()].map(([l, n]) => `${l} ${n}`).join(", ");
    console.log(`test-craft: clean — ${checked} test file(s) (${langs}).`);
    return 0;
  }

  const byFile = new Map();
  for (const v of all) {
    if (!byFile.has(v.file)) byFile.set(v.file, []);
    byFile.get(v.file).push(v);
  }
  for (const [file, vs] of byFile) {
    console.log(`\n${file}`);
    for (const v of vs.sort((a, b) => a.line - b.line)) {
      console.log(`  ${String(v.line).padStart(5)}:  ${v.rule}`);
      console.log(`         ${v.why}`);
    }
  }

  const byRule = new Map();
  for (const v of all) byRule.set(v.rule, (byRule.get(v.rule) ?? 0) + 1);

  console.log(`\n${"-".repeat(74)}`);
  console.log(`test-craft: ${all.length} finding(s) in ${byFile.size} file(s); ${checked} test file(s) checked.`);
  for (const [rule, n] of [...byRule].sort((a, b) => b[1] - a[1])) {
    console.log(`  ${String(n).padStart(4)}  ${rule}`);
  }
  if (byRule.has("focused-test")) {
    console.log(`\n  focused-test is the urgent one: the rest of that file is not running.`);
  }
  console.log(`\nFix them, or annotate the genuinely-correct ones:  test-allow: <rule-id> — <reason>`);
  return 1;
}

/* --------------------------------------------------------------- self-test */

function selfTest() {
  const problems = [];
  const t = (name, cond) => { if (!cond) problems.push(name); };
  const cfg = { ...DEFAULTS };

  // File detection across conventions.
  t("detect: js spec", isTestFile("src/a.test.ts", cfg));
  t("detect: python", isTestFile("tests/test_thing.py", cfg));
  t("detect: go", isTestFile("pkg/thing_test.go", cfg));
  t("detect: java", isTestFile("src/ThingTest.java", cfg));
  t("detect: by directory", isTestFile("spec/whatever.rb", cfg));
  t("detect: not a test", !isTestFile("src/thing.ts", cfg));

  const js = LANGS[".js"];
  t("js: focus detected", anyMatch(js.focus, "  it.only('x', () => {"));
  t("js: describe.only detected", anyMatch(js.focus, "describe.only('suite', () => {"));
  t("js: skip detected", anyMatch(js.skip, "  it.skip('x', () => {"));
  t("js: assertion detected", anyMatch(js.assert, "    expect(a).toBe(1)"));
  t("js: sleep detected", anyMatch(js.sleep, "    await new Promise(resolve => setTimeout(resolve, 500))"));
  t("js: plain it is a case", anyMatch(js.case, "  it('does a thing', () => {"));

  const py = LANGS[".py"];
  t("py: case", anyMatch(py.case, "def test_thing():"));
  t("py: assertion", anyMatch(py.assert, "    assert x == 1"));
  t("py: unittest assertion", anyMatch(py.assert, "    self.assertEqual(a, b)"));
  t("py: sleep", anyMatch(py.sleep, "    time.sleep(2)"));
  t("py: skip", anyMatch(py.skip, "@pytest.mark.skip"));

  const go = LANGS[".go"];
  t("go: case", anyMatch(go.case, "func TestThing(t *testing.T) {"));
  t("go: assertion", anyMatch(go.assert, "\t\tt.Fatalf(\"want %v\", x)"));
  t("go: skip", anyMatch(go.skip, "\tt.Skip(\"later\")"));
  t("go: sleep", anyMatch(go.sleep, "\ttime.Sleep(time.Second)"));

  t("java: case", anyMatch(LANGS[".java"].case, "    @Test"));
  t("java: skip", anyMatch(LANGS[".java"].skip, "    @Disabled"));
  t("rust: case", anyMatch(LANGS[".rs"].case, "#[test]"));
  t("rust: skip", anyMatch(LANGS[".rs"].skip, "#[ignore]"));
  t("cs: case", anyMatch(LANGS[".cs"].case, "    [Fact]"));
  t("rb: focus", anyMatch(LANGS[".rb"].focus, "  fit 'works' do"));

  // Escape hatch
  t("allow: with reason", parseAllow("// test-allow: sleep-in-test \u2014 third-party poll interval")?.reason === "third-party poll interval");
  t("allow: missing reason", parseAllow("# test-allow: focused-test")?.reason === "");

  // Every language entry must be well formed.
  for (const [ext, l] of Object.entries(LANGS)) {
    if (!l.name || !l.comment?.length) problems.push(`lang ${ext} malformed`);
    for (const key of ["case", "focus", "skip", "assert", "sleep"]) {
      if (!Array.isArray(l[key])) problems.push(`lang ${ext} missing ${key}`);
    }
  }

  if (problems.length) {
    console.error("FAIL: test-craft self-test\n  " + problems.join("\n  "));
    return 1;
  }
  console.log(`PASS: test-craft self-test (${Object.keys(LANGS).length} extensions, ${new Set(Object.values(LANGS).map((l) => l.name)).size} languages)`);
  return 0;
}

/* -------------------------------------------------------------------- main */

function main() {
  const argv = process.argv.slice(2);

  if (argv.includes("--help") || argv.includes("-h")) {
    console.log(`
test-craft — the test checker

  node check-tests.mjs [paths...]   check test files (default: .)
  node check-tests.mjs --json       machine-readable
  node check-tests.mjs --langs      list recognized languages
  node check-tests.mjs --self-test

Rules: focused-test, skipped-test, no-assertion, sleep-in-test,
       loop-in-test, empty-test, huge-test-file, unexplained-escape

focused-test is the one that matters most: a committed .only silently disables
every other test in the file while CI stays green.

Escape hatch, on the line or the line above (any comment syntax):
  test-allow: <rule-id> — <reason>

Config from .test-craft.json:
${JSON.stringify(DEFAULTS, null, 2)}
`);
    return 0;
  }

  if (argv.includes("--self-test")) return selfTest();

  if (argv.includes("--langs")) {
    const byName = new Map();
    for (const [ext, l] of Object.entries(LANGS)) {
      if (!byName.has(l.name)) byName.set(l.name, []);
      byName.get(l.name).push(ext);
    }
    console.log("Recognized languages:\n");
    for (const [name, exts] of [...byName].sort()) console.log(`  ${name.padEnd(24)} ${exts.join(" ")}`);
    console.log(`\nAnything else is skipped, never guessed at.`);
    return 0;
  }

  const paths = argv.filter((a) => !a.startsWith("--"));
  return run(paths.length ? paths : ["."], { json: argv.includes("--json") });
}

process.exit(main());

