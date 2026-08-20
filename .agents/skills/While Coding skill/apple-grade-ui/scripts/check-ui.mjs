#!/usr/bin/env node
/**
 * APPLE-GRADE UI — THE CHECKER
 *
 * Zero dependencies. Node 18+. Two modes:
 *
 *   node check-ui.mjs [paths...]              lint source files for token violations
 *   node check-ui.mjs --tokens tokens.css     print a WCAG contrast report
 *
 * With no paths it scans the current directory, skipping node_modules, build
 * output, and any file whose name contains "token".
 *
 * EXIT CODES
 *   0  clean
 *   1  violations found (or a contrast pair below its floor)
 *   2  bad usage / unreadable input
 *
 * ESCAPE HATCH
 * A violation that is genuinely correct is annotated on the offending line, or
 * on the line directly above it:
 *
 *   // ui-allow: raw-hex — browser chrome color cannot reference a CSS variable
 *
 * The rule id and a reason are both required. An escape with no reason is
 * itself reported, because an unexplained escape is a violation someone hid.
 *
 * WHY A SCRIPT AND NOT A CHECKLIST
 * Every rule below is mechanically decidable. Mechanically decidable rules
 * belong in a program with an exit code, not in a document that an author
 * grades themselves against.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, extname, basename, relative, resolve } from "node:path";

/* ------------------------------------------------------------------ config */

const SOURCE_EXT = new Set([
  ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
  ".css", ".scss", ".vue", ".svelte", ".astro", ".html",
]);

const SKIP_DIR = new Set([
  "node_modules", ".git", "dist", "build", ".next", ".nuxt", ".svelte-kit",
  "out", "coverage", "vendor", ".turbo", ".cache", "__snapshots__",
]);

// Files that legitimately contain raw values: this is where tokens are DEFINED.
const isTokenFile = (p) => /token|theme|palette|design-system/i.test(basename(p));

/* Extension families.
 * A CSS property means the same thing in every file, but it is SPELLED
 * differently depending on where it lives, so the rules that look for one name
 * the family they apply to instead of testing extensions inline.
 *   CSS_LIKE — literal CSS: a stylesheet, a <style> block, a style="" attribute
 *   JS_LIKE  — camelCase inline-style objects, and CSS-in-JS template literals
 */
const CSS_LIKE = new Set([".css", ".scss", ".vue", ".svelte", ".astro", ".html"]);
const JS_LIKE  = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);

/**
 * A CSS declaration occupying its own line, as it appears inside a
 * styled-components / emotion template literal:  `  font-size: 15px;`
 *
 * Anchoring to the start of the line is what keeps these rules off prose,
 * comments, and identifiers that merely MENTION a property name — the
 * false-positive class that makes a linter get switched off.
 */
const cssDecl = (prop, value) => new RegExp(`^\\s*${prop}\\s*:\\s*${value}`);

/* ------------------------------------------------------------------- rules */

/**
 * Each rule: { id, why, test(line, ctx) -> boolean, appliesTo(ext) -> boolean }
 * `why` is printed with the violation — a rule the author does not understand
 * is a rule the author routes around.
 */
const RULES = [
  {
    id: "raw-hex",
    why: "Colors come from tokens so dark mode, contrast, and theming stay correct in one place.",
    appliesTo: () => true,
    test: (line) =>
      // #abc / #aabbcc / #aabbccdd, not inside a url() or an id selector context
      /#[0-9a-fA-F]{3,8}\b/.test(line) &&
      !/url\(|&#|#[0-9a-fA-F]*[g-zG-Z]/.test(line),
  },
  {
    id: "arbitrary-value",
    why: "Tailwind bracket values bypass the scale. If the value you need is not on the scale, the scale is the thing to change.",
    appliesTo: (e) => e !== ".css" && e !== ".scss",
    test: (line) =>
      /\b(?:text|bg|p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|w|h|gap|rounded|border|shadow|leading|tracking|duration|delay|z|top|left|right|bottom|inset|translate|scale|opacity)-\[[^\]]+\]/.test(line),
  },
  {
    id: "default-palette",
    why: "Tailwind's stock grays and colors have no dark-mode counterpart and no semantic meaning. Use label / surface / fill / accent.",
    appliesTo: () => true,
    test: (line) =>
      /\b(?:text|bg|border|ring|fill|stroke|from|via|to|divide|outline|decoration|shadow|accent|caret|placeholder)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/.test(line),
  },
  {
    id: "default-shadow",
    why: "Tailwind's shadows are tight and dark — they read as Material Design. Use shadow-e1..e4, which are large, soft, and two-layered.",
    appliesTo: () => true,
    test: (line) => /\bshadow-(?:sm|md|lg|xl|2xl)\b/.test(line),
  },
  {
    // ui-allow: transition-all — this is the rule's own id, not a usage
    id: "transition-all",
    why: "It animates properties you did not intend, including ones that trigger layout, and it cannot be audited. Name the properties.",
    appliesTo: () => true,
    test: (line) =>
      /\btransition-all\b/.test(line) ||
      /transition(?:-property)?\s*:\s*all\b/.test(line),
  },
  {
    id: "type-override",
    why: "Each of the eleven type steps already carries its line-height and tracking. If you need different metrics, you picked the wrong step.",
    appliesTo: (e) => e !== ".css" && e !== ".scss",
    test: (line) => {
      const hasType = /\btext-(?:display|title-[123]|headline|body|callout|subhead|footnote|caption-[12])\b/.test(line);
      const hasOverride = /\b(?:leading|tracking)-(?!none\b)[a-z0-9.\[]/.test(line);
      return hasType && hasOverride;
    },
  },
  {
    id: "raw-backdrop-blur",
    why: "Translucent chrome uses the material-* tokens, which carry the correct blur, tint, saturation boost, and opaque fallback.",
    appliesTo: () => true,
    test: (line) => /\bbackdrop-blur-(?:sm|md|lg|xl|2xl|3xl|\[)/.test(line),
  },
  {
    id: "px-font-size",
    why: "Font sizes in px do not respond to browser zoom or OS text-size settings. The scale is defined in rem.",
    appliesTo: (e) => CSS_LIKE.has(e) || JS_LIKE.has(e),
    test: (line, ctx) =>
      CSS_LIKE.has(ctx.ext)
        ? /font-size\s*:\s*\d+px/.test(line)
        : /\bfontSize\s*:\s*["'`]\s*\d+px/.test(line) ||  // JSX inline style
          cssDecl("font-size", "\\d+px").test(line),      // CSS-in-JS literal
  },
  {
    id: "div-onclick",
    why: "A div is not focusable, does not fire on Enter or Space, and announces nothing. Use <button> or <a>.",
    appliesTo: (e) => e === ".tsx" || e === ".jsx" || e === ".vue" || e === ".svelte" || e === ".astro" || e === ".html",
    test: (line) => /<(?:div|span)\b[^>]*\bon[Cc]lick\b/.test(line),
  },
  {
    id: "outline-none",
    why: "Removing the outline without a :focus-visible replacement strands every keyboard user. This is the most common shipped a11y failure.",
    appliesTo: () => true,
    test: (line, ctx) =>
      (/outline\s*:\s*none/.test(line) || /\boutline-none\b/.test(line)) &&
      !ctx.fileHasFocusVisible,
  },
  {
    id: "viewport-lock",
    why: "Blocking zoom is a WCAG failure and breaks the product for anyone who needs larger text.",
    appliesTo: () => true,
    test: (line) => /user-scalable\s*=\s*no|maximum-scale\s*=\s*1(?![\d.])/.test(line),
  },
  {
    id: "will-change-permanent",
    why: "A permanent will-change holds a compositor layer forever and costs memory. Add it before the animation, remove it after.",
    appliesTo: (e) => CSS_LIKE.has(e) || JS_LIKE.has(e),
    test: (line, ctx) =>
      CSS_LIKE.has(ctx.ext)
        ? /will-change\s*:\s*(?!auto)/.test(line)
        : /\bwillChange\s*:\s*["'`]\s*(?!auto)/.test(line) ||  // JSX inline style
          cssDecl("will-change", "(?!auto)").test(line),       // CSS-in-JS literal
  },
];

/* --------------------------------------------------------------- lint mode */

function collectFiles(target, acc = []) {
  let st;
  try { st = statSync(target); } catch { return acc; }

  if (st.isDirectory()) {
    if (SKIP_DIR.has(basename(target))) return acc;
    for (const entry of readdirSync(target)) collectFiles(join(target, entry), acc);
    return acc;
  }
  if (SOURCE_EXT.has(extname(target))) acc.push(target);
  return acc;
}

/** Parse `ui-allow: rule-id — reason` from a line. Returns {id, reason} or null.
 *
 * The separator must have whitespace on BOTH sides. Every rule id here is
 * hyphenated, so an escape naming `raw-hex` with no reason would otherwise
 * parse as id="raw" + reason="hex" — silently breaking the suppression AND
 * hiding the missing reason. Requiring surrounding whitespace disambiguates the
 * separator from a hyphen inside the id. */
function parseAllow(line) {
  const m = /ui-allow:\s*([a-z0-9-]+?)\s+[—–-]\s+(.+?)\s*(?:\*\/|-->|$)/.exec(line);
  if (m) return { id: m[1], reason: m[2].trim() };
  const bare = /ui-allow:\s*([a-z0-9-]+)/.exec(line);
  if (bare) return { id: bare[1], reason: "" };
  return null;
}

function lintFile(path, rootDir) {
  const rel = relative(rootDir, path) || path;
  if (isTokenFile(path)) return { violations: [], skipped: rel };

  let text;
  try { text = readFileSync(path, "utf8"); } catch { return { violations: [] }; }

  const lines = text.split(/\r?\n/);
  const ext = extname(path);
  const ctx = { ext, fileHasFocusVisible: /:focus-visible|focus-visible:/.test(text) };
  const violations = [];

  lines.forEach((line, i) => {
    const allowHere = parseAllow(line);
    const allowAbove = i > 0 ? parseAllow(lines[i - 1]) : null;

    // An escape with no stated reason is itself a finding — reported once, on
    // the line it actually appears. Checking allowAbove here too would report
    // the same escape a second time against the line below it.
    if (allowHere && allowHere.reason === "") {
      violations.push({
        file: rel, line: i + 1, rule: "unexplained-escape",
        why: "An escape hatch with no stated reason is a violation someone hid. Write why after an em dash.",
        text: line.trim(),
      });
    }

    for (const rule of RULES) {
      if (!rule.appliesTo(ext)) continue;
      if ((allowHere && allowHere.id === rule.id) || (allowAbove && allowAbove.id === rule.id)) continue;
      if (rule.test(line, ctx)) {
        violations.push({ file: rel, line: i + 1, rule: rule.id, why: rule.why, text: line.trim() });
      }
    }
  });

  return { violations };
}

function runLint(targets) {
  const rootDir = process.cwd();
  const files = targets.flatMap((t) => collectFiles(resolve(t)));

  if (files.length === 0) {
    console.log("No source files found. Nothing to check.");
    return 0;
  }

  const all = [];
  let skipped = 0;
  for (const f of files) {
    const r = lintFile(f, rootDir);
    if (r.skipped) skipped++;
    all.push(...r.violations);
  }

  const byRule = new Map();
  for (const v of all) byRule.set(v.rule, (byRule.get(v.rule) ?? 0) + 1);

  if (all.length === 0) {
    console.log(`apple-grade-ui: clean — ${files.length} files checked, ${skipped} token file(s) skipped.`);
    return 0;
  }

  // Group by file so the output is walkable top to bottom.
  const byFile = new Map();
  for (const v of all) {
    if (!byFile.has(v.file)) byFile.set(v.file, []);
    byFile.get(v.file).push(v);
  }

  for (const [file, vs] of byFile) {
    console.log(`\n${file}`);
    for (const v of vs) {
      console.log(`  ${String(v.line).padStart(5)}:  ${v.rule}`);
      console.log(`         ${v.text.slice(0, 120)}`);
      console.log(`         → ${v.why}`);
    }
  }

  console.log(`\n${"-".repeat(72)}`);
  console.log(`apple-grade-ui: ${all.length} violation(s) in ${byFile.size} file(s), ${files.length} checked.`);
  for (const [rule, n] of [...byRule].sort((a, b) => b[1] - a[1])) {
    console.log(`  ${String(n).padStart(4)}  ${rule}`);
  }
  console.log(`\nFix them, or annotate the genuinely-correct ones:  // ui-allow: <rule-id> — <reason>`);
  return 1;
}

/* ----------------------------------------------------------- contrast mode */

function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

/** Walk the CSS and return [{ chain: string, decls: Map }] for every block. */
function parseBlocks(css) {
  const out = [];
  const stack = [];
  let i = 0, selStart = 0;

  while (i < css.length) {
    const ch = css[i];
    if (ch === "{") {
      const selector = css.slice(selStart, i).trim().replace(/\s+/g, " ");
      stack.push({ selector, bodyStart: i + 1, decls: new Map() });
      selStart = i + 1;
      i++;
    } else if (ch === "}") {
      const block = stack.pop();
      if (block) {
        // Declarations directly in this block (nested blocks already consumed).
        const body = css.slice(block.bodyStart, i);
        const flat = body.replace(/\{[^{}]*\}/g, "");
        for (const m of flat.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
          block.decls.set(m[1], m[2].trim());
        }
        if (block.decls.size) {
          out.push({
            chain: [...stack.map((s) => s.selector), block.selector].join(" >> "),
            decls: block.decls,
          });
        }
      }
      selStart = i + 1;
      i++;
    } else {
      i++;
    }
  }
  return out;
}

const isDarkChain = (chain) =>
  /prefers-color-scheme\s*:\s*dark/.test(chain) ||
  /\[data-theme\s*=\s*["']dark["']\]/.test(chain) ||
  /(^|[\s,>])\.dark\b/.test(chain);

function collectVars(css) {
  const blocks = parseBlocks(css);
  const light = new Map();
  const dark = new Map();

  for (const b of blocks) {
    if (isDarkChain(b.chain)) continue;
    if (/prefers-contrast|prefers-reduced/.test(b.chain)) continue;
    for (const [k, v] of b.decls) light.set(k, v);
  }
  for (const [k, v] of light) dark.set(k, v);
  for (const b of blocks) {
    if (!isDarkChain(b.chain)) continue;
    if (/prefers-contrast|prefers-reduced/.test(b.chain)) continue;
    for (const [k, v] of b.decls) dark.set(k, v);
  }
  return { light, dark };
}

function resolveVar(name, vars, seen = new Set()) {
  if (seen.has(name)) return null;
  seen.add(name);
  let v = vars.get(name);
  if (!v) return null;
  const m = /^var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+))?\)$/.exec(v.trim());
  if (m) return resolveVar(m[1], vars, seen) ?? (m[2] ? m[2].trim() : null);
  return v;
}

/** Parse #rgb / #rrggbb / rgb() / rgba() into {r,g,b,a} or null. */
function parseColor(value) {
  if (!value) return null;
  const v = value.trim();

  let m = /^#([0-9a-fA-F]{3,8})$/.exec(v);
  if (m) {
    let h = m[1];
    if (h.length === 3) h = [...h].map((c) => c + c).join("");
    if (h.length === 6) h += "ff";
    if (h.length !== 8) return null;
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
      a: parseInt(h.slice(6, 8), 16) / 255,
    };
  }

  m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+%?))?\s*\)$/.exec(v);
  if (m) {
    let a = 1;
    if (m[4] != null) a = m[4].endsWith("%") ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
    return { r: +m[1], g: +m[2], b: +m[3], a };
  }
  return null; // color-mix(), oklch(), named colors — not evaluated
}

const composite = (fg, bg) => ({
  r: fg.a * fg.r + (1 - fg.a) * bg.r,
  g: fg.a * fg.g + (1 - fg.a) * bg.g,
  b: fg.a * fg.b + (1 - fg.a) * bg.b,
  a: 1,
});

function luminance({ r, g, b }) {
  const f = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function ratio(fg, bg) {
  const L1 = luminance(fg), L2 = luminance(bg);
  const [hi, lo] = L1 > L2 ? [L1, L2] : [L2, L1];
  return (hi + 0.05) / (lo + 0.05);
}

// [foreground, background, required, note]
// "expected to FAIL" marks a pair that is deliberately below the floor and is
// therefore restricted to decorative use. It reports BY DESIGN, not FAIL.
const PAIRS = [
  ["--label",           "--surface", 4.5, "primary text on a card"],
  ["--label-secondary", "--surface", 4.5, "subtitles and descriptions"],
  ["--label-tertiary",  "--surface", 4.5, "placeholders — expected to FAIL; legal only for text nobody must read"],
  ["--label",           "--canvas",  4.5, "text directly on the page"],
  ["--label-secondary", "--canvas",  4.5, "secondary text on the page"],
  ["--accent-text",     "--surface", 4.5, "links and accent wording"],
  ["--label-on-accent", "--accent",  4.5, "text inside a filled primary button"],
  ["--success-text",    "--surface", 4.5, "positive status wording"],
  ["--warning-text",    "--surface", 4.5, "caution wording — the trap: raw orange never passes here"],
  ["--danger-text",     "--surface", 4.5, "error wording"],
  ["--info-text",       "--surface", 4.5, "informational wording"],
  ["--ai-text",         "--surface", 4.5, "AI-attribution wording"],
  ["--accent",          "--surface", 3.0, "a filled accent control against the surface behind it"],
  ["--border-control",  "--surface", 3.0, "input borders and control outlines — these carry meaning"],
  ["--separator",       "--surface", 3.0, "row divider — expected to FAIL; decorative, spacing is the real separator"],
];

function contrastReport(vars, modeLabel) {
  const rows = [];
  let failures = 0;

  for (const [fgName, bgName, need, note] of PAIRS) {
    const fgRaw = resolveVar(fgName, vars);
    const bgRaw = resolveVar(bgName, vars);
    const fg = parseColor(fgRaw);
    const bg = parseColor(bgRaw);

    if (!fg || !bg) {
      rows.push({ fgName, bgName, need, note, value: null,
        status: fgRaw || bgRaw ? "SKIP" : "MISSING" });
      continue;
    }

    const flat = composite(fg, bg);
    const r = ratio(flat, bg);
    const expectedFail = /expected to FAIL/.test(note);
    const ok = r >= need;
    if (!ok && !expectedFail) failures++;
    rows.push({ fgName, bgName, need, note, value: r,
      status: ok ? "PASS" : expectedFail ? "BY DESIGN" : "FAIL" });
  }

  console.log(`\n${modeLabel}`);
  console.log("-".repeat(96));
  for (const row of rows) {
    const shown = row.value == null ? "  n/a " : `${row.value.toFixed(2)}:1`.padStart(7);
    const status = row.status.padEnd(9);
    console.log(`  ${status} ${shown}  need ${row.need.toFixed(1)}:1   ${row.fgName} on ${row.bgName}`);
    if (row.status === "FAIL" || row.status === "SKIP" || row.status === "MISSING") {
      console.log(`             ${row.note}`);
      if (row.status === "SKIP") {
        console.log(`             value could not be evaluated (color-mix / oklch / named color) — verify by hand`);
      }
    }
  }
  return failures;
}

function runContrast(tokenPath) {
  let css;
  try { css = readFileSync(tokenPath, "utf8"); }
  catch (e) { console.error(`Cannot read ${tokenPath}: ${e.message}`); return 2; }

  const { light, dark } = collectVars(stripComments(css));
  if (light.size === 0) {
    console.error(`No custom properties found in ${tokenPath}.`);
    return 2;
  }

  console.log(`Contrast report — ${tokenPath}`);
  console.log(`${light.size} tokens in light, ${dark.size} in dark.`);

  const failLight = contrastReport(light, "LIGHT MODE");
  const failDark = contrastReport(dark, "DARK MODE");
  const total = failLight + failDark;

  console.log(`\n${"=".repeat(96)}`);
  if (total === 0) {
    console.log("All evaluated pairs meet their floor. Pairs marked SKIP still need a manual check.");
    return 0;
  }
  console.log(`${total} pair(s) below the contrast floor. Adjust the token, not the checklist.`);
  return 1;
}

/* ------------------------------------------------------------ setup verify */

/**
 * The silent failure this catches:
 *
 * Someone copies tokens.css in, writes `bg-surface text-body shadow-e1`
 * everywhere, and never wires the Tailwind preset. Every one of those classes
 * then resolves to NOTHING. The page does not error — it renders unstyled and
 * merely looks plain, which is the hardest kind of wrong to notice and the
 * easiest to ship. The lint pass cannot see it, because the source is correct.
 *
 * So this checks the wiring itself, mechanically, before any of it matters.
 */
function runVerifySetup(root) {
  const found = { tokens: null, tailwindConfig: null, v4Theme: null, importedIn: [] };
  const files = collectFiles(resolve(root));

  // Config files are not in SOURCE_EXT, so look for them directly.
  for (const name of ["tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs", "tailwind.config.cjs"]) {
    const p = join(resolve(root), name);
    try { statSync(p); found.tailwindConfig = p; break; } catch { /* keep looking */ }
  }

  for (const f of files) {
    let text;
    try { text = readFileSync(f, "utf8"); } catch { continue; }

    // The token layer is identified by what it DEFINES, not by its filename.
    if (!found.tokens && /--brand-accent\s*:/.test(text)) found.tokens = f;
    // Tailwind v4 needs no preset — an @theme block does the same job.
    if (!found.v4Theme && /@theme\b/.test(text)) found.v4Theme = f;
    if (/@import\s+["'][^"']*token|from\s+["'][^"']*token/i.test(text)) found.importedIn.push(f);
  }

  const results = [];
  const add = (ok, label, detail) => results.push({ ok, label, detail });

  add(!!found.tokens, "Token layer present",
    found.tokens ? relative(resolve(root), found.tokens) : "no file defines --brand-accent — copy assets/tokens.css in");

  const presetWired = found.tailwindConfig
    ? /presets\s*:/.test(readFileSync(found.tailwindConfig, "utf8"))
    : false;

  if (found.v4Theme) {
    add(true, "Tailwind v4 @theme block", relative(resolve(root), found.v4Theme));
  } else if (found.tailwindConfig) {
    add(presetWired, "Tailwind preset wired",
      presetWired
        ? relative(resolve(root), found.tailwindConfig)
        : `${relative(resolve(root), found.tailwindConfig)} has no \`presets:\` key — every token class will silently do nothing`);
  } else {
    add(false, "Tailwind config or v4 @theme",
      "neither found. If the project does not use Tailwind, the token CSS still works — ignore this line.");
  }

  add(found.importedIn.length > 0, "Token layer imported",
    found.importedIn.length
      ? `${found.importedIn.length} file(s)`
      : "nothing imports the token file — it must be imported before any other stylesheet");

  console.log(`\napple-grade-ui setup — ${resolve(root)}\n${"-".repeat(72)}`);
  for (const r of results) {
    console.log(`  ${r.ok ? "OK  " : "FAIL"}  ${r.label.padEnd(28)} ${r.detail}`);
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`${"-".repeat(72)}`);
  if (failed === 0) {
    console.log("Setup looks correct. Now run the contrast report and the lint pass.\n");
    return 0;
  }
  console.log(`${failed} setup problem(s). Fix these before writing UI — every token class\n` +
              `depends on them, and when they are wrong nothing errors, it just looks cheap.\n`);
  return 1;
}

/* --------------------------------------------------------------- self-test */

/**
 * Proves the checker still works after a change. Every other script in this
 * skill family ships one; without it a refactor can silently disable a rule and
 * every subsequent run reports a comfortable, meaningless "clean".
 */
function selfTest() {
  const problems = [];
  const t = (name, cond) => { if (!cond) problems.push(name); };
  const fire = (id, line, ext = ".tsx", ctx = {}) => {
    const rule = RULES.find((r) => r.id === id);
    if (!rule) { problems.push(`no such rule: ${id}`); return false; }
    if (!rule.appliesTo(ext)) return false;
    return rule.test(line, { ext, fileHasFocusVisible: false, ...ctx });
  };

  /* Each rule fires on a real violation. Every fixture below is a code-shaped
     STRING, so the checker reads them as violations of the very rules they
     test — each one carries its own escape. */
  t("raw-hex fires", fire("raw-hex", 'color: "#0A5AFF"')); // ui-allow: raw-hex — fixture for this rule
  t("arbitrary-value fires", fire("arbitrary-value", 'className="text-[13px]"')); // ui-allow: arbitrary-value — fixture
  t("default-palette fires", fire("default-palette", 'className="text-gray-500"')); // ui-allow: default-palette — fixture
  t("default-shadow fires", fire("default-shadow", 'className="shadow-md"')); // ui-allow: default-shadow — fixture
  t("transition-all fires", fire("transition-all", 'className="transition-all"')); // ui-allow: transition-all — fixture
  t("type-override fires", fire("type-override", 'className="text-body leading-6"')); // ui-allow: type-override — fixture
  t("raw-backdrop-blur fires", fire("raw-backdrop-blur", 'className="backdrop-blur-md"')); // ui-allow: raw-backdrop-blur — fixture
  t("div-onclick fires", fire("div-onclick", "<div onClick={go}>")); // ui-allow: div-onclick — fixture
  t("outline-none fires", fire("outline-none", "outline: none;", ".css")); // ui-allow: outline-none — fixture
  t("viewport-lock fires", fire("viewport-lock", '<meta content="user-scalable=no">', ".html")); // ui-allow: viewport-lock — fixture
  t("px-font-size fires (css)", fire("px-font-size", "  font-size: 13px;", ".css"));
  t("will-change fires (css)", fire("will-change-permanent", "  will-change: transform;", ".css"));

  // The CSS-in-JS / JSX narrowing: camelCase in JS, kebab only at line start.
  t("px-font-size fires on JSX inline", fire("px-font-size", 'style={{ fontSize: "13px" }}', ".tsx")); // ui-allow: px-font-size — fixture
  t("px-font-size fires in styled literal", fire("px-font-size", "  font-size: 15px;", ".tsx"));
  t("will-change fires on JSX inline", fire("will-change-permanent", 'style={{ willChange: "transform" }}', ".tsx")); // ui-allow: will-change-permanent — fixture
  t("willChange auto is allowed", !fire("will-change-permanent", 'style={{ willChange: "auto" }}', ".tsx"));

  // False positives that would get the tool switched off.
  t("prose comment not flagged", !fire("will-change-permanent", "// avoid will-change here", ".ts"));
  t("string mentioning font-size not flagged", !fire("px-font-size", 'const doc = "px sizes are banned";', ".ts"));
  t("token-scale class not flagged", !fire("default-palette", 'className="text-label-secondary"'));
  t("shadow-e1 not flagged", !fire("default-shadow", 'className="shadow-e1"'));
  t("focus-visible suppresses outline-none",
    !RULES.find((r) => r.id === "outline-none").test("outline: none;", { ext: ".css", fileHasFocusVisible: true }));

  // The escape hatch. Rule ids are hyphenated, so a bare escape must NOT parse
  // its own id as id + reason — that bug silently disabled every suppression.
  t("allow: parses reason", parseAllow("// ui-allow: raw-hex — partner brand asset")?.reason === "partner brand asset");
  t("allow: keeps hyphenated id", parseAllow("// ui-allow: raw-hex — why")?.id === "raw-hex");
  // ui-allow: unexplained-escape — the next two lines are fixtures for exactly this case
  t("allow: bare id keeps full id", parseAllow("// ui-allow: arbitrary-value")?.id === "arbitrary-value"); // ui-allow: unexplained-escape — fixture
  t("allow: bare id has no reason", parseAllow("// ui-allow: arbitrary-value")?.reason === ""); // ui-allow: unexplained-escape — fixture
  t("allow: ascii hyphen separator", parseAllow("# ui-allow: default-shadow - legacy")?.reason === "legacy");

  // Contrast maths, against known values.
  const white = parseColor("#FFFFFF"); // ui-allow: raw-hex — the contrast maths needs literal endpoints
  const black = parseColor("#000000"); // ui-allow: raw-hex — the contrast maths needs literal endpoints
  t("parses hex", white && white.r === 255 && white.a === 1);
  t("parses rgba", parseColor("rgba(0, 0, 0, 0.5)")?.a === 0.5);
  t("black on white is 21:1", Math.round(ratio(black, white)) === 21);
  t("identical colors are 1:1", Math.round(ratio(white, white)) === 1);
  t("unknown format returns null", parseColor("oklch(0.7 0.1 200)") === null);

  // Rule table integrity.
  const ids = RULES.map((r) => r.id);
  if (new Set(ids).size !== ids.length) problems.push("duplicate rule id");
  for (const r of RULES) {
    if (!r.id || !r.why || typeof r.test !== "function" || typeof r.appliesTo !== "function") {
      problems.push(`rule ${r.id} malformed`);
    }
    try { r.test("const x = 1;", { ext: ".ts", fileHasFocusVisible: false }); }
    catch { problems.push(`rule ${r.id} throws on a plain line`); }
  }

  if (problems.length) {
    console.error("FAIL: apple-grade-ui self-test\n  " + problems.join("\n  "));
    return 1;
  }
  console.log(`PASS: apple-grade-ui self-test (${RULES.length} rules)`);
  return 0;
}

/* -------------------------------------------------------------------- main */

function main() {
  const argv = process.argv.slice(2);

  if (argv.includes("--help") || argv.includes("-h")) {
    console.log(`
apple-grade-ui checker

  node check-ui.mjs [paths...]           lint source files (default: .)
  node check-ui.mjs --tokens <file>      WCAG contrast report for a token file
  node check-ui.mjs --verify-setup [dir] check the token layer is actually wired up
  node check-ui.mjs --self-test          prove the checker itself still works

Run them in that order on a new project: setup, then contrast, then lint.

Escape hatch, on the offending line or the line above it:
  // ui-allow: <rule-id> — <reason>

Rules: ${RULES.map((r) => r.id).join(", ")}
`);
    return 0;
  }

  if (argv.includes("--self-test")) return selfTest();

  const vi = argv.indexOf("--verify-setup");
  if (vi !== -1) return runVerifySetup(argv[vi + 1] ?? ".");

  const ti = argv.indexOf("--tokens");
  if (ti !== -1) {
    const file = argv[ti + 1];
    if (!file) { console.error("--tokens needs a file path"); return 2; }
    return runContrast(file);
  }

  return runLint(argv.length ? argv : ["."]);
}

process.exit(main());
