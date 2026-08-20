#!/usr/bin/env node
/**
 * CODE CRAFT â€” THE STRUCTURAL CHECKER
 *
 * Zero dependencies. Node 18+.
 *
 *   node check-code.mjs [paths...]     check files (default: .)
 *   node check-code.mjs --json         machine-readable
 *   node check-code.mjs --langs        list recognized languages
 *   node check-code.mjs --self-test
 *
 * EXIT CODES
 *   0  clean
 *   1  violations found
 *   2  bad usage / unreadable input
 *
 * ESCAPE HATCH, on the offending line or the line above it:
 *   craft-allow: <rule-id> â€” <reason>
 * Works with any language's comment syntax, because it is matched as text. A
 * reason is required; an unexplained escape is itself reported.
 *
 * â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
 * WHY THESE RULES AND NOT OTHERS
 *
 * This checks only what is TRUE IN EVERY LANGUAGE and mechanically decidable:
 * how long a unit is, how deeply it nests, how many parameters it takes,
 * whether a failure is silently discarded, whether dead code was left behind.
 *
 * It does NOT check naming quality, whether an abstraction is earned, or
 * whether two similar functions change for the same reason. Those need
 * judgment, and a checker that pretends to have judgment produces confident
 * wrong answers, which is worse than no answer. Those live in the references
 * and in review.
 *
 * ON UNKNOWN LANGUAGES
 * An unrecognized extension is skipped and counted, never guessed at. A false
 * finding trains people to ignore the tool, and a tool that is ignored is worse
 * than one that was never installed.
 *
 * craft-allow: god-file â€” one copy-paste artifact carrying 18 language
 * definitions; splitting it would defeat the point of installing a single file
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, extname, basename, relative, resolve } from "node:path";

/* ------------------------------------------------------------------ config */

const DEFAULTS = {
  maxFileLines: 400,
  maxFunctionLines: 50,
  maxNesting: 3,
  maxParams: 4,
  maxLineLength: 120,
};

const SKIP_DIR = new Set([
  "node_modules", ".git", "dist", "build", ".next", ".nuxt", ".svelte-kit",
  "out", "coverage", "vendor", ".turbo", ".cache", "target", "__pycache__",
  ".venv", "venv", "env", ".gradle", "bin", "obj", "Pods", ".terraform",
  "migrations", "generated", "__generated__", ".idea", ".vscode",
]);

/** Generated or vendored code is not craftsmanship's business. */
const SKIP_FILE = /\.(min|bundle|generated|gen|pb|g)\.[a-z]+$|_pb2?\.py$|\.d\.ts$|-lock\./i;

/* --------------------------------------------------------------- languages
 *
 * `block` â€” how a unit's body is delimited:
 *   "brace"  { ... }         C-family
 *   "indent" leading spaces  Python-family
 *   "end"    do ... end      Ruby/Lua/Elixir-family
 *
 * `func` â€” patterns that begin a callable unit. Deliberately permissive: a
 * missed function costs a missed finding, while a false match costs trust.
 * ------------------------------------------------------------------------ */

const LANGS = {
  ".js":    { name: "JavaScript", block: "brace",  line: ["//"], naming: "camel" },
  ".mjs":   { name: "JavaScript", block: "brace",  line: ["//"], naming: "camel" },
  ".cjs":   { name: "JavaScript", block: "brace",  line: ["//"], naming: "camel" },
  ".jsx":   { name: "JavaScript", block: "brace",  line: ["//"], naming: "camel" },
  ".ts":    { name: "TypeScript", block: "brace",  line: ["//"], naming: "camel" },
  ".tsx":   { name: "TypeScript", block: "brace",  line: ["//"], naming: "camel" },
  ".java":  { name: "Java",       block: "brace",  line: ["//"], naming: "camel" },
  ".kt":    { name: "Kotlin",     block: "brace",  line: ["//"], naming: "camel" },
  ".scala": { name: "Scala",      block: "brace",  line: ["//"], naming: "camel" },
  ".cs":    { name: "C#",         block: "brace",  line: ["//"], naming: "pascal" },
  ".go":    { name: "Go",         block: "brace",  line: ["//"], naming: "camel" },
  ".rs":    { name: "Rust",       block: "brace",  line: ["//"], naming: "snake" },
  ".swift": { name: "Swift",      block: "brace",  line: ["//"], naming: "camel" },
  ".c":     { name: "C",          block: "brace",  line: ["//"], naming: "snake" },
  ".h":     { name: "C",          block: "brace",  line: ["//"], naming: "snake" },
  ".cpp":   { name: "C++",        block: "brace",  line: ["//"], naming: "snake" },
  ".hpp":   { name: "C++",        block: "brace",  line: ["//"], naming: "snake" },
  ".cc":    { name: "C++",        block: "brace",  line: ["//"], naming: "snake" },
  ".php":   { name: "PHP",        block: "brace",  line: ["//", "#"], naming: "camel" },
  ".dart":  { name: "Dart",       block: "brace",  line: ["//"], naming: "camel" },
  ".py":    { name: "Python",     block: "indent", line: ["#"], naming: "snake" },
  ".rb":    { name: "Ruby",       block: "end",    line: ["#"], naming: "snake" },
  ".ex":    { name: "Elixir",     block: "end",    line: ["#"], naming: "snake" },
  ".exs":   { name: "Elixir",     block: "end",    line: ["#"], naming: "snake" },
  ".lua":   { name: "Lua",        block: "end",    line: ["--"], naming: "snake" },
  ".sh":    { name: "Shell",      block: "brace",  line: ["#"], naming: "snake" },
  ".bash":  { name: "Shell",      block: "brace",  line: ["#"], naming: "snake" },
};

/** Patterns that open a callable unit, by block style. */
const FUNC_START = {
  brace: [
    /\bfunction\s+[A-Za-z_$]/,                    // JS/PHP
    /\bfunc\s+(\([^)]*\)\s*)?[A-Za-z_]/,          // Go (incl. methods)
    /\bfn\s+[a-z_]/,                              // Rust
    /\bfun\s+[A-Za-z_]/,                          // Kotlin
    // Java / C# / Kotlin: modifiers, then a return type, then name and body.
    // craft-allow: long-line â€” one regex; wrapping it would hurt readability
    /\b(?:public|private|protected|internal|static|final|override|async|suspend)[\w\s<>,\[\]]*\s+[A-Za-z_]\w*\s*\([^;]*\)\s*\{/,
    /\bdef\s+[A-Za-z_]/,                          // Scala
    /\bfunc\s+[A-Za-z_]/,                         // Swift
    /^[\w<>:,\s*&]+\s+[A-Za-z_]\w*\s*\([^;]*\)\s*\{/, // C/C++ definition
    /\b(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>)/, // JS assigned
    /^\s*[A-Za-z_$][\w$]*\s*\([^)]*\)\s*\{/,      // method shorthand
  ],
  indent: [/^\s*(?:async\s+)?def\s+[A-Za-z_]/],
  end:    [/^\s*(?:def|defp)\s+[A-Za-z_]/, /^\s*function\s+[A-Za-z_]/],
};

/**
 * Control-flow keywords that look exactly like a call at the start of a line:
 * `while (a) {` matches the method-shorthand pattern above. Without this guard
 * every loop and conditional is counted as a function, which both invents
 * findings and corrupts the real ones.
 */
const NOT_A_FUNCTION = new RegExp(
  "^\\s*(?:if|else|for|while|switch|catch|do|try|finally|with|match|when|" +
  "guard|return|await|yield|throw|new|typeof|delete|in|of)\\b",
);

/** Empty-failure-handler patterns. The single most expensive line in software. */
const SWALLOWED = [
  /catch\s*\([^)]*\)\s*\{\s*\}/,                 // C-family, one line
  /catch\s*\{\s*\}/,                             // C#
  /except[^:]*:\s*pass\s*$/,                      // Python
  /rescue\s*(?:=>\s*\w+\s*)?$/,                   // Ruby bare rescue (checked with next line)
  /\.catch\s*\(\s*(?:\(\s*\)|[\w$]+)\s*=>\s*\{\s*\}\s*\)/, // JS promise
  /if\s+err\s*!=\s*nil\s*\{\s*\}/,                // Go
  /let\s+_\s*=\s*.*;\s*\/\/\s*ignore/i,           // Rust explicit-but-unexplained
];

/* -------------------------------------------------------------------- rules */

function loadConfig(root) {
  const p = join(root, ".code-craft.json");
  if (!existsSync(p)) return { ...DEFAULTS };
  try {
    const parsed = JSON.parse(readFileSync(p, "utf8"));
    return { ...DEFAULTS, ...parsed };
  } catch {
    process.stderr.write(`warning: ${p} is not valid JSON â€” using defaults\n`);
    return { ...DEFAULTS };
  }
}

const isComment = (line, lang) =>
  lang.line.some((c) => line.trimStart().startsWith(c));

/** Strip strings and comments so braces inside them do not shift depth. */
function decommented(line, lang) {
  let out = line;
  out = out.replace(/"(?:[^"\\]|\\.)*"/g, '""').replace(/'(?:[^'\\]|\\.)*'/g, "''");
  out = out.replace(/`(?:[^`\\]|\\.)*`/g, "``");
  for (const c of lang.line) {
    const i = out.indexOf(c);
    if (i !== -1) out = out.slice(0, i);
  }
  return out;
}

/**
 * The declared name of a callable, tried in order of specificity.
 *
 * Each pattern is anchored to something structural rather than scanning for
 * "an identifier", because a loose scan picks up return types and parameter
 * types instead â€” `fn process(a: u32) -> u32` yields "u32", which is worse than
 * useless in a finding.
 */
function extractName(raw) {
  // Keyword-declared, with an optional receiver: `func (r *T) Name(`
  let m = /(?:function|func|fn|fun|def|defp|sub)\s+(?:\([^)]*\)\s*)?([A-Za-z_$][\w$]*)/.exec(raw);
  if (m) return m[1];
  // Assigned function expression: `const handler = (a) => {`
  m = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=/.exec(raw);
  if (m) return m[1];
  // Typed declaration (Java, C#, C, C++, Swift): the identifier before `(`.
  // Modifiers and return types are not followed by `(`, so this lands on the name.
  m = /([A-Za-z_$][\w$]*)\s*\(/.exec(raw);
  if (m) return m[1];
  return "anonymous";
}

/** Parameters on a signature line, excluding the implicit receiver. */
function countParams(raw) {
  const paren = /\(([^)]*)\)/.exec(raw);
  if (!paren || !paren[1].trim()) return 0;
  const isReceiver = (s) => /^(?:self|cls|&?self|&mut self)$/.test(s.trim());
  return paren[1].split(",").filter((s) => s.trim() && !isReceiver(s)).length;
}

/* Each extent finder returns { endLine, maxDepth }, or endLine -1 when the end
   cannot be determined confidently â€” in which case the unit is dropped rather
   than reported with a guessed length. */

// craft-allow: deep-nesting â€” a character scanner is inherently lineâ†’charâ†’branch
function extentBrace(lines, start, lang) {
  let depth = 0, maxDepth = 0, opened = false;
  for (let j = start; j < lines.length; j++) {
    for (const ch of decommented(lines[j], lang)) {
      if (ch === "{") { depth++; opened = true; maxDepth = Math.max(maxDepth, depth); }
      else if (ch === "}") depth--;
    }
    if (opened && depth <= 0) return { endLine: j, maxDepth };
  }
  return { endLine: -1, maxDepth };
}

function extentIndent(lines, start) {
  const base = lines[start].length - lines[start].trimStart().length;
  let deepest = base, j = start + 1;
  for (; j < lines.length; j++) {
    if (lines[j].trim() === "") continue;
    const ind = lines[j].length - lines[j].trimStart().length;
    if (ind <= base) break;
    deepest = Math.max(deepest, ind);
  }
  // Walk back over trailing blank lines: they sit between definitions and
  // belong to neither, so counting them inflates every function's length.
  let end = j - 1;
  while (end > start && lines[end].trim() === "") end--;
  // Indentation is conventionally 4 spaces; derive nesting depth from that.
  return { endLine: end, maxDepth: Math.round((deepest - base) / 4) };
}

const OPENS_BLOCK = /\b(?:def|defp|do|if|unless|case|while|for|begin|function)\b/;

function extentEnd(lines, start, lang) {
  let depth = 0, maxDepth = 0;
  for (let j = start; j < lines.length; j++) {
    const code = decommented(lines[j], lang);
    if (OPENS_BLOCK.test(code)) depth++;
    if (/\bend\b/.test(code)) depth--;
    maxDepth = Math.max(maxDepth, depth);
    if (depth <= 0 && j > start) return { endLine: j, maxDepth };
  }
  return { endLine: -1, maxDepth };
}

const EXTENT = { brace: extentBrace, indent: extentIndent, end: extentEnd };

/**
 * Find callable units and their extent.
 * Returns [{ name, startLine, endLine, lines, maxDepth, params }].
 */
function findFunctions(lines, lang) {
  const patterns = FUNC_START[lang.block] ?? [];
  const measure = EXTENT[lang.block];
  if (!measure) return [];
  const found = [];

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    if (isComment(raw, lang) || NOT_A_FUNCTION.test(raw)) continue;
    if (!patterns.some((p) => p.test(raw))) continue;

    const { endLine, maxDepth } = measure(lines, i, lang);
    if (endLine === -1) continue;

    found.push({
      name: extractName(raw),
      startLine: i + 1,
      endLine: endLine + 1,
      lines: endLine - i + 1,
      maxDepth,
      params: countParams(raw),
    });
  }
  return found;
}

/** Consecutive comment lines that look like code rather than prose. */
function findCommentedCode(lines, lang) {
  const hits = [];
  let run = [];
  const looksLikeCode = (t) =>
    /[;{}]\s*$/.test(t) ||
    /^\s*(?:if|for|while|return|const|let|var|def|func|fn|class|import|from|public|private)\b/.test(t) ||
    /^\s*[\w.$]+\s*\([^)]*\)\s*;?\s*$/.test(t) ||
    /^\s*[\w$]+\s*=\s*.+$/.test(t);

  const flush = () => {
    if (run.length >= 2) hits.push({ line: run[0].n, count: run.length });
    run = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    if (!isComment(raw, lang)) { flush(); continue; }
    let text = raw.trimStart();
    for (const c of lang.line) if (text.startsWith(c)) text = text.slice(c.length);
    if (looksLikeCode(text)) run.push({ n: i + 1 });
    else flush();
  }
  flush();
  return hits;
}

/* The separator must have whitespace on BOTH sides. Rule ids are hyphenated, so
   an escape naming `god-file` with no reason would otherwise parse as id="god"
   + reason="file" â€” silently breaking suppression and hiding the missing
   reason. Surrounding whitespace disambiguates it from a hyphen in the id. */
function parseAllow(line) {
  const m = /craft-allow:\s*([a-z0-9-]+?)\s+[â€”â€“-]\s+(.+?)\s*(?:\*\/|-->|$)/.exec(line);
  if (m) return { id: m[1], reason: m[2].trim() };
  const bare = /craft-allow:\s*([a-z0-9-]+)/.exec(line);
  if (bare) return { id: bare[1], reason: "" };
  return null;
}

/* ---------------------------------------------------------------- checking */

// The nesting here is helper closures (allowAt, add), not control flow.
// craft-allow: long-function â€” one file's checks, read as a sequence
function checkFile(path, root, cfg) { // craft-allow: deep-nesting â€” closures, not branching
  const ext = extname(path);
  const lang = LANGS[ext];
  const rel = relative(root, path) || path;
  if (!lang) return { skipped: true, rel };

  let text;
  try { text = readFileSync(path, "utf8"); } catch { return { skipped: true, rel }; }
  const lines = text.split(/\r?\n/);
  const out = [];

  const allowAt = (n, id) => {
    const here = parseAllow(lines[n - 1] ?? "");
    const above = parseAllow(lines[n - 2] ?? "");
    return (here && here.id === id) || (above && above.id === id);
  };

  /* File-level findings are reported at line 1, which may be a shebang â€” there
     is no line above it to annotate. So a file-level rule accepts its escape
     anywhere in the file's header, before the first non-comment line. */
  const allowInHeader = (id) => {
    for (const l of lines.slice(0, 40)) {
      const a = parseAllow(l);
      if (a && a.id === id) return true;
    }
    return false;
  };
  const add = (line, rule, why) => {
    if (!allowAt(line, rule)) out.push({ file: rel, line, rule, why, lang: lang.name });
  };

  // Unexplained escapes are themselves findings. Routed through `add` so that
  // a deliberate one â€” a test fixture, a doc example â€” can itself be annotated.
  lines.forEach((l, i) => {
    const a = parseAllow(l);
    if (a && a.reason === "") {
      add(i + 1, "unexplained-escape",
        "An escape with no stated reason is a violation someone hid. Write why after an em dash.");
    }
  });

  // Law 10 â€” a file that holds everything is a file nobody can hold.
  const code = lines.filter((l) => l.trim() && !isComment(l, lang)).length;
  if (code > cfg.maxFileLines && !allowInHeader("god-file")) {
    add(1, "god-file",
      `${code} code lines (limit ${cfg.maxFileLines}). A file this size has more than one reason to change.`);
  }

  checkUnits(lines, lang, cfg, add);
  checkLines(lines, lang, cfg, add);

  for (const c of findCommentedCode(lines, lang)) {
    add(c.line, "commented-out-code",
      `${c.count} lines of commented-out code. Version control remembers it; readers should not have to.`);
  }

  return { violations: out, rel, lang: lang.name };
}

/** Per-callable checks: Laws 2 and 3. */
function checkUnits(lines, lang, cfg, add) {
  for (const f of findFunctions(lines, lang)) {
    if (f.lines > cfg.maxFunctionLines) {
      add(f.startLine, "long-function",
        `"${f.name}" is ${f.lines} lines (limit ${cfg.maxFunctionLines}). Law 2: one thing, one level of abstraction.`);
    }
    if (f.maxDepth > cfg.maxNesting) {
      add(f.startLine, "deep-nesting",
        `"${f.name}" nests ${f.maxDepth} deep (limit ${cfg.maxNesting}). Law 3: return early, guard clauses first.`);
    }
    if (f.params > cfg.maxParams) {
      add(f.startLine, "many-params",
        `"${f.name}" takes ${f.params} parameters (limit ${cfg.maxParams}). Group them into a named structure.`);
    }
  }
}

const TODO_TAG = /\b(TODO|FIXME|HACK|XXX)\b/;
const TODO_REF = /(#\d+|[A-Z]{2,}-\d+|https?:\/\/)/;
const SWALLOW_MSG =
  "A discarded failure becomes a silent wrong answer. Handle it, propagate it, or state why it is ignored.";

/** Per-line checks: Laws 5 and 10. */
function checkLines(lines, lang, cfg, add) { // craft-allow: deep-nesting â€” one callback, flat checks
  lines.forEach((raw, i) => {
    const n = i + 1;

    // craft-allow: unowned-todo â€” naming the tag in the rule that detects it
    // Law 10 â€” an untracked task marker is permanent.
    if (isComment(raw, lang)) {
      if (TODO_TAG.test(raw) && !TODO_REF.test(raw)) {
        add(n, "unowned-todo", "TODO/FIXME with no ticket or link. Untracked, it is permanent â€” file it or fix it.");
      }
      return;
    }

    if (raw.length > cfg.maxLineLength) {
      add(n, "long-line", `${raw.length} chars (limit ${cfg.maxLineLength}).`);
    }
    // Law 5 â€” the most expensive line in software.
    if (SWALLOWED.some((p) => p.test(raw))) {
      add(n, "swallowed-error", SWALLOW_MSG);
    }
    // Multi-line empty handler: an opening catch followed immediately by a close.
    if (/catch\s*(\([^)]*\))?\s*\{\s*$/.test(raw) && /^\s*\}/.test(lines[i + 1] ?? "")) {
      add(n, "swallowed-error", "Empty catch block. " + SWALLOW_MSG);
    }
    // A bare Python except swallows everything, including KeyboardInterrupt.
    if (/^\s*except\s*:\s*$/.test(raw)) {
      add(n, "swallowed-error",
        "Bare except catches everything, including KeyboardInterrupt and SystemExit. Name the exception.");
    }
  });
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
  if (!SKIP_FILE.test(basename(target))) acc.push(target);
  return acc;
}

// Splitting this would scatter one output format across several functions.
// craft-allow: long-function â€” sequential report assembly, read top to bottom
function run(targets, { json = false } = {}) {
  const root = process.cwd();
  const cfg = loadConfig(root);
  const files = targets.flatMap((t) => collect(resolve(t)));

  const all = [];
  const langCount = new Map();
  let checked = 0, skipped = 0;

  for (const f of files) {
    const r = checkFile(f, root, cfg);
    if (r.skipped) { skipped++; continue; }
    checked++;
    langCount.set(r.lang, (langCount.get(r.lang) ?? 0) + 1);
    all.push(...r.violations);
  }

  if (json) {
    console.log(JSON.stringify({ checked, skipped, violations: all }, null, 2));
    return all.length ? 1 : 0;
  }

  if (checked === 0) {
    console.log(`code-craft: no recognized source files. ${skipped} skipped.`);
    console.log(`Recognized: ${[...new Set(Object.values(LANGS).map((l) => l.name))].join(", ")}`);
    return 0;
  }

  if (all.length === 0) {
    const langs = [...langCount.entries()].map(([l, n]) => `${l} ${n}`).join(", ");
    console.log(`code-craft: clean â€” ${checked} file(s) checked (${langs}), ${skipped} skipped.`);
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
  console.log(
    `code-craft: ${all.length} finding(s) in ${byFile.size} file(s); ${checked} checked, ${skipped} skipped.`);
  for (const [rule, n] of [...byRule].sort((a, b) => b[1] - a[1])) {
    console.log(`  ${String(n).padStart(4)}  ${rule}`);
  }
  console.log(`\nFix them, or annotate the genuinely-correct ones:  craft-allow: <rule-id> â€” <reason>`);
  console.log(`Thresholds differ legitimately by language and product type â€” override in .code-craft.json`);
  return 1;
}

/* --------------------------------------------------------------- self-test */

// Grouping these assertions into helpers would hide what is being tested. The
// fixtures below are code-shaped strings, so the checker reads them as
// functions too â€” correct behavior, and unavoidable for test data.
// craft-allow: long-function â€” a flat list of assertions, deliberately
function selfTest() {
  const problems = [];
  const t = (name, cond) => { if (!cond) problems.push(name); };

  // Brace: a 4-deep function must be caught.
  const js = [ // craft-allow: long-function â€” code-shaped fixture strings
    "function outer(a, b) {",
    "  if (a) {",
    "    if (b) {",
    "      while (a) {",
    "        doThing();",
    "      }",
    "    }",
    "  }",
    "}",
  ];
  const jsFns = findFunctions(js, LANGS[".js"]);
  t("brace: finds one function", jsFns.length === 1);
  t("brace: measures length", jsFns[0]?.lines === 9);
  t("brace: measures depth", jsFns[0]?.maxDepth === 4);
  t("brace: counts params", jsFns[0]?.params === 2);

  // Indent: Python extent and depth.
  // craft-allow: long-function â€” code-shaped fixture strings
  const py = ["def outer(a, b):", "    if a:", "        if b:", "            return 1", "    return 0", "", "x = 1"];
  const pyFns = findFunctions(py, LANGS[".py"]);
  t("indent: finds one function", pyFns.length === 1);
  t("indent: stops at dedent", pyFns[0]?.endLine === 5);
  t("indent: measures depth", pyFns[0]?.maxDepth === 3);

  // `self` must not count as a parameter.
  const pySelf = findFunctions(["def m(self, a):", "    return a"], LANGS[".py"]);
  t("indent: ignores self", pySelf[0]?.params === 1);

  // end-block: Ruby.
  const rb = ["def thing", "  if x", "    y", "  end", "end"];
  const rbFns = findFunctions(rb, LANGS[".rb"]);
  t("end: finds one function", rbFns.length === 1);
  t("end: measures length", rbFns[0]?.lines === 5);

  // Braces inside strings must not shift depth.
  const strFns = findFunctions(['function f() {', '  const s = "}{";', '  return s;', '}'], LANGS[".js"]);
  t("brace: ignores braces in strings", strFns.length === 1 && strFns[0].lines === 4);

  // craft-allow: swallowed-error â€” these are the detector's own test fixtures
  t("swallow: js inline", SWALLOWED.some((p) => p.test("try { x() } catch (e) {}")));
  t("swallow: python", SWALLOWED.some((p) => p.test("except ValueError: pass")));
  // craft-allow: swallowed-error â€” the detector's own test fixture
  t("swallow: go", SWALLOWED.some((p) => p.test("if err != nil {}")));

  // Commented-out code vs prose.
  const cc = findCommentedCode(
    ["// const x = 1;", "// doThing();", "// this explains why", "// and continues"], LANGS[".js"]);
  t("commented-code: flags code", cc.length === 1 && cc[0].count === 2);
  t("commented-code: ignores prose", cc.every((h) => h.count === 2));

  // Escape hatch. Both fixtures below are escapes-as-test-data, not real ones.
  const withReason = parseAllow("// craft-allow: long-function â€” generated parser");
  t("allow: parses with reason", withReason?.reason === "generated parser");
  // craft-allow: unexplained-escape â€” fixture for the missing-reason case
  t("allow: flags missing reason", parseAllow("# craft-allow: god-file")?.reason === "");

  // Names must be the DECLARED name, not a return type or a parameter type.
  t("name: python", extractName("def process(a, b):") === "process");
  t("name: go func", extractName("func Process(a int) error {") === "Process");
  t("name: go method", extractName("func (r *Repo) Save(x T) error {") === "Save");
  t("name: rust", extractName("fn process(a: u32) -> u32 {") === "process");
  t("name: java", extractName("    public void process(int a) {") === "process");
  t("name: kotlin", extractName("fun process(a: Int) {") === "process");
  t("name: ruby", extractName("def process(a, b)") === "process");
  t("name: js assigned", extractName("const handler = (a) => {") === "handler");
  t("name: csharp", extractName("private async Task<int> Compute(int a) {") === "Compute");

  // Every language entry must be well formed.
  for (const [ext, l] of Object.entries(LANGS)) {
    if (!l.name || !l.block || !l.line?.length) problems.push(`lang ${ext} malformed`);
    if (!FUNC_START[l.block]) problems.push(`lang ${ext} has no patterns for block style ${l.block}`);
  }

  if (problems.length) {
    console.error("FAIL: code-craft self-test\n  " + problems.join("\n  "));
    return 1;
  }
  const languageCount = new Set(Object.values(LANGS).map((l) => l.name)).size;
  console.log(
    `PASS: code-craft self-test (${Object.keys(LANGS).length} extensions, ${languageCount} languages)`);
  return 0;
}

/* -------------------------------------------------------------------- main */

function main() {
  const argv = process.argv.slice(2);

  if (argv.includes("--help") || argv.includes("-h")) {
    console.log(`
code-craft â€” the structural checker

  node check-code.mjs [paths...]   check files (default: .)
  node check-code.mjs --json       machine-readable
  node check-code.mjs --langs      list recognized languages
  node check-code.mjs --self-test

Rules: god-file, long-function, deep-nesting, many-params, long-line,
       swallowed-error, unowned-todo, commented-out-code, unexplained-escape

Escape hatch, on the line or the line above (any comment syntax):
  craft-allow: <rule-id> â€” <reason>

Thresholds come from .code-craft.json when present:
${JSON.stringify(DEFAULTS, null, 2)}

This checks structure only. Naming quality, earned abstraction, and whether two
similar functions change for the same reason need judgment â€” see the references.
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
    for (const [name, exts] of [...byName].sort()) {
      console.log(`  ${name.padEnd(12)} ${exts.join(" ")}`);
    }
    console.log(`\nAnything else is skipped, never guessed at.`);
    return 0;
  }

  const paths = argv.filter((a) => !a.startsWith("--"));
  return run(paths.length ? paths : ["."], { json: argv.includes("--json") });
}

process.exit(main());

