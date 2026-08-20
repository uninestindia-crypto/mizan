#!/usr/bin/env node
/**
 * API CRAFT — THE CONTRACT CHECKER
 *
 * Zero dependencies. Node 18+.
 *
 *   node check-api.mjs [paths...]   check the contract (default: .)
 *   node check-api.mjs --json       machine-readable
 *   node check-api.mjs --self-test
 *
 * EXIT CODES
 *   0  clean (or nothing checkable was found)
 *   1  findings
 *   2  bad usage
 *
 * ESCAPE HATCH, on the offending line or the line above it:
 *   api-allow: <rule-id> — <reason>
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * TWO SOURCES, IN ORDER OF PREFERENCE
 *
 * 1. AN OPENAPI / SWAGGER DOCUMENT. The richest source: it states paths,
 *    methods, parameters, and responses, so pagination and documented errors
 *    become checkable, not just path shape.
 * 2. ROUTE REGISTRATIONS IN SOURCE. When there is no spec, routes are found by
 *    the patterns every common framework uses. Only path-shaped rules apply.
 *
 * If neither is found, this reports UNKNOWN and exits 0. A checker that invents
 * findings on a project it does not understand gets switched off, and then it
 * protects nothing.
 *
 * WHAT IT DELIBERATELY DOES NOT CHECK
 * Whether a resource is the right abstraction, whether a field means what its
 * name claims, whether a change is genuinely compatible for real consumers.
 * Those need judgment; they are in the references and belong in review.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, extname, basename, relative, resolve } from "node:path";

/* ------------------------------------------------------------------ config */

const SKIP_DIR = new Set([
  "node_modules", ".git", "dist", "build", ".next", ".nuxt", "out", "coverage",
  "vendor", ".turbo", ".cache", "target", "__pycache__", ".venv", "venv",
]);

const SOURCE_EXT = new Set([
  ".js", ".mjs", ".cjs", ".ts", ".tsx", ".py", ".go", ".rb", ".php",
  ".java", ".kt", ".cs", ".rs", ".ex",
]);

const SPEC_NAME = /^(openapi|swagger|api)\.(json|ya?ml)$/i;

/* ------------------------------------------------------------------- rules */

/** Path segments that are a version marker. */
const VERSION_SEG = /^v\d+(?:[a-z0-9.-]*)?$/i;

/** Verbs that should never appear in a path — the method is the verb (Law 8). */
const PATH_VERB = new RegExp(
  "(^|[/_-])(get|post|put|patch|delete|create|update|remove|fetch|list|" +
  "retrieve|add|edit|save|insert|destroy|find|search|do|make|set)" +
  "([/_-]|[A-Z]|$)",
);

/** Names that mean "give me a page of this". */
const PAGING_PARAM = /^(limit|per_page|perpage|pagesize|page_size|page|offset|cursor|after|before|first|last|start|top|skip|max_results|maxresults|count|size)$/i;

/* ---------------------------------------------------------------- gathering */

function walk(target, acc = []) {
  let st;
  try { st = statSync(target); } catch { return acc; }
  if (st.isDirectory()) {
    if (SKIP_DIR.has(basename(target))) return acc;
    for (const e of readdirSync(target)) walk(join(target, e), acc);
    return acc;
  }
  acc.push(target);
  return acc;
}

const read = (p) => { try { return readFileSync(p, "utf8"); } catch { return ""; } };

/* ------------------------------------------------------------ spec parsing */

/**
 * Extract { path, method, params[], responses[] } from an OpenAPI document.
 *
 * JSON is parsed properly. YAML is scanned line-wise for the handful of shapes
 * that matter, because a full YAML parser is not worth a dependency here and a
 * partial one that silently mis-parses would be worse than the line scan.
 */
function parseSpecJson(text) {
  let doc;
  try { doc = JSON.parse(text); } catch { return null; }
  if (!doc || typeof doc !== "object" || !doc.paths) return null;

  const ops = [];
  for (const [path, item] of Object.entries(doc.paths)) {
    if (!item || typeof item !== "object") continue;
    const shared = Array.isArray(item.parameters) ? item.parameters : [];
    for (const [method, op] of Object.entries(item)) {
      if (!/^(get|post|put|patch|delete|head|options)$/i.test(method)) continue;
      if (!op || typeof op !== "object") continue;
      const params = [...shared, ...(Array.isArray(op.parameters) ? op.parameters : [])]
        .map((p) => (p && typeof p === "object" ? String(p.name ?? "") : ""))
        .filter(Boolean);
      ops.push({
        path,
        method: method.toUpperCase(),
        params,
        responses: Object.keys(op.responses ?? {}),
        line: 1,
      });
    }
  }
  return ops;
}

function parseSpecYaml(text) {
  const lines = text.split(/\r?\n/);
  const ops = [];
  let inPaths = false, pathsIndent = 0;
  let curPath = null, curPathIndent = 0;
  let cur = null;

  const flush = () => { if (cur) { ops.push(cur); cur = null; } };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    if (!raw.trim() || raw.trimStart().startsWith("#")) continue;
    const indent = raw.length - raw.trimStart().length;
    const t = raw.trim();

    if (/^paths\s*:/.test(t)) { inPaths = true; pathsIndent = indent; continue; }
    if (inPaths && indent <= pathsIndent && !/^paths\s*:/.test(t)) { flush(); inPaths = false; }
    if (!inPaths) continue;

    const pathMatch = /^("?)(\/[^\s:"]*)\1\s*:/.exec(t);
    if (pathMatch && indent > pathsIndent) {
      flush();
      curPath = pathMatch[2];
      curPathIndent = indent;
      continue;
    }
    const methodMatch = /^(get|post|put|patch|delete|head|options)\s*:/i.exec(t);
    if (methodMatch && curPath && indent > curPathIndent) {
      flush();
      cur = { path: curPath, method: methodMatch[1].toUpperCase(), params: [], responses: [], line: i + 1 };
      continue;
    }
    if (!cur) continue;

    const nameMatch = /^-?\s*name\s*:\s*["']?([A-Za-z0-9_\[\]-]+)["']?/.exec(t);
    if (nameMatch) cur.params.push(nameMatch[1]);
    const codeMatch = /^["']?(\d{3})["']?\s*:/.exec(t);
    if (codeMatch) cur.responses.push(codeMatch[1]);
  }
  flush();
  return ops;
}

/* --------------------------------------------------------- route scanning */

/**
 * Route registrations across frameworks. Each pattern yields method + path.
 * Permissive on purpose: a missed route costs a missed finding, a false match
 * costs trust.
 */
const ROUTE_PATTERNS = [
  // express / fastify / koa-router / hapi:  app.get("/x", ...)
  /\.\s*(get|post|put|patch|delete)\s*\(\s*["'`]([^"'`]+)["'`]/gi,
  // flask / fastapi:  @app.get("/x")   @app.route("/x", methods=["POST"])
  /@\w+\.(get|post|put|patch|delete|route)\s*\(\s*["']([^"']+)["']/gi,
  // spring:  @GetMapping("/x")
  /@(Get|Post|Put|Patch|Delete)Mapping\s*\(\s*(?:value\s*=\s*)?["']([^"']+)["']/g,
  // gin / echo / chi:  r.GET("/x", h)
  /\.\s*(GET|POST|PUT|PATCH|DELETE)\s*\(\s*["`]([^"`]+)["`]/g,
  // rails routes.rb:  get "/x" => ...
  /^\s*(get|post|put|patch|delete)\s+["']([^"']+)["']/gim,
  // django path("x/", ...) — method unknown
  /\b(path|re_path)\s*\(\s*r?["']([^"']*)["']/g,
];

function scanRoutes(file, text) {
  const found = [];
  const lines = text.split(/\r?\n/);
  for (const pattern of ROUTE_PATTERNS) {
    pattern.lastIndex = 0;
    let m;
    while ((m = pattern.exec(text)) !== null) {
      const method = m[1].toUpperCase();
      const path = m[2];
      if (!path.startsWith("/") && !/^[a-z0-9]/i.test(path)) continue;
      const line = text.slice(0, m.index).split(/\r?\n/).length;
      found.push({
        file,
        path: path.startsWith("/") ? path : "/" + path,
        method: /^(PATH|RE_PATH|ROUTE)$/.test(method) ? "ANY" : method,
        params: [],
        responses: [],
        line,
        raw: lines[line - 1] ?? "",
      });
    }
  }
  return found;
}

/* ---------------------------------------------------------------- checking */

function parseAllow(line) {
  const m = /api-allow:\s*([a-z0-9-]+?)\s+[—–-]\s+(.+?)\s*(?:\*\/|-->|$)/.exec(line);
  if (m) return { id: m[1], reason: m[2].trim() };
  const bare = /api-allow:\s*([a-z0-9-]+)/.exec(line);
  if (bare) return { id: bare[1], reason: "" };
  return null;
}

/** A path that looks like a collection: ends in a plural noun, no id segment. */
function isCollectionPath(path) {
  const segs = path.split("/").filter(Boolean);
  if (segs.length === 0) return false;
  const last = segs[segs.length - 1];
  if (/^[:{<]/.test(last) || /^</.test(last)) return false;   // ends in a param
  if (/^\$?\{/.test(last)) return false;
  return /s$/i.test(last) && !/(status|address|series)$/i.test(last);
}

function checkOperations(ops, { fromSpec }) {
  const findings = [];
  const add = (op, rule, why) => findings.push({ ...op, rule, why });

  for (const op of ops) {
    // Law 3 — a version segment, present from the first release.
    const segs = op.path.split("/").filter(Boolean);
    if (!segs.some((s) => VERSION_SEG.test(s))) {
      add(op, "unversioned-path",
        `"${op.path}" has no version segment. Retrofitting one onto a live API means supporting an unnamed legacy contract forever.`);
    }

    // Law 8 — the method is the verb.
    for (const s of segs) {
      if (/^[:{<$]/.test(s)) continue; // a parameter, not a literal
      if (PATH_VERB.test(s)) {
        add(op, "verb-in-path",
          `"${op.path}" puts an action in the path. The method is the verb — use ${op.method} on a noun.`);
        break;
      }
    }

    // Law 6 — every list is paginated.
    if ((op.method === "GET" || op.method === "ANY") && isCollectionPath(op.path)) {
      if (fromSpec && !op.params.some((p) => PAGING_PARAM.test(p))) {
        add(op, "unpaginated-list",
          `"${op.path}" returns a collection with no pagination parameter. It works at 40 rows and fails at 4 million.`);
      }
    }

    // Law 7 — errors are part of the contract.
    if (fromSpec && op.responses.length > 0) {
      const hasError = op.responses.some((c) => /^[45]/.test(c) || /default/i.test(c));
      if (!hasError) {
        add(op, "undocumented-errors",
          `${op.method} ${op.path} documents only success responses. A consumer cannot handle what the contract does not describe.`);
      }
    }

    // Consistency: trailing slashes split every client cache and route table.
    if (op.path.length > 1 && op.path.endsWith("/")) {
      add(op, "trailing-slash",
        `"${op.path}" ends in a slash. Pick one convention; two spellings of one resource is two resources to every cache.`);
    }

    // Naming: paths are lowercase and hyphenated, not camelCase.
    if (/[A-Z]/.test(op.path.replace(/\{[^}]*\}/g, ""))) {
      add(op, "path-case",
        `"${op.path}" mixes case. Paths are lowercase; some proxies and clients treat case differently.`);
    }
  }
  return findings;
}

/* -------------------------------------------------------------------- run */

function run(targets, { json = false } = {}) {
  const root = process.cwd();
  const files = targets.flatMap((t) => walk(resolve(t)));

  const specFiles = files.filter((f) => SPEC_NAME.test(basename(f)));
  let ops = [];
  let source = "none";
  const seen = new Map();

  for (const f of specFiles) {
    const text = read(f);
    const parsed = extname(f).toLowerCase() === ".json" ? parseSpecJson(text) : parseSpecYaml(text);
    if (parsed && parsed.length) {
      ops.push(...parsed.map((o) => ({ ...o, file: relative(root, f) || f })));
      source = "spec";
    }
  }

  if (ops.length === 0) {
    for (const f of files) {
      if (!SOURCE_EXT.has(extname(f))) continue;
      const text = read(f);
      if (!/\b(get|post|put|patch|delete|route|path|Mapping)\b/i.test(text)) continue;
      const routes = scanRoutes(relative(root, f) || f, text);
      for (const r of routes) {
        const key = `${r.method} ${r.path}`;
        if (seen.has(key)) continue;
        seen.set(key, true);
        ops.push(r);
      }
    }
    if (ops.length) source = "routes";
  }

  if (ops.length === 0) {
    if (json) { console.log(JSON.stringify({ source: "none", findings: [] }, null, 2)); return 0; }
    console.log("api-craft: UNKNOWN — no OpenAPI document and no recognizable routes found.");
    console.log("           Nothing was checked. Add a spec, or check the contract by hand");
    console.log("           against references/08-review-checklist.md.");
    return 0;
  }

  let findings = checkOperations(ops, { fromSpec: source === "spec" });

  // Honour the escape hatch, where the finding points at a real source line.
  findings = findings.filter((f) => {
    if (!f.file) return true;
    const lines = read(join(root, f.file)).split(/\r?\n/);
    const here = parseAllow(lines[f.line - 1] ?? "");
    const above = parseAllow(lines[f.line - 2] ?? "");
    return !((here && here.id === f.rule) || (above && above.id === f.rule));
  });

  if (json) {
    console.log(JSON.stringify({ source, operations: ops.length, findings }, null, 2));
    return findings.length ? 1 : 0;
  }

  const label = source === "spec" ? "OpenAPI document" : "route registrations in source";
  if (findings.length === 0) {
    console.log(`api-craft: clean — ${ops.length} operation(s) from ${label}.`);
    return 0;
  }

  const byFile = new Map();
  for (const f of findings) {
    const k = f.file ?? "(contract)";
    if (!byFile.has(k)) byFile.set(k, []);
    byFile.get(k).push(f);
  }

  for (const [file, fs] of byFile) {
    console.log(`\n${file}`);
    for (const f of fs.sort((a, b) => a.line - b.line)) {
      console.log(`  ${String(f.line).padStart(5)}:  ${f.rule}   ${f.method} ${f.path}`);
      console.log(`         ${f.why}`);
    }
  }

  const byRule = new Map();
  for (const f of findings) byRule.set(f.rule, (byRule.get(f.rule) ?? 0) + 1);

  console.log(`\n${"-".repeat(74)}`);
  console.log(`api-craft: ${findings.length} finding(s) across ${ops.length} operation(s), from ${label}.`);
  for (const [rule, n] of [...byRule].sort((a, b) => b[1] - a[1])) {
    console.log(`  ${String(n).padStart(4)}  ${rule}`);
  }
  if (source === "routes") {
    console.log(`\nOnly path-shaped rules ran. Pagination and error-documentation checks`);
    console.log(`need an OpenAPI document — which is also what consumers need.`);
  }
  console.log(`\nFix them, or annotate the genuinely-correct ones:  api-allow: <rule-id> — <reason>`);
  return 1;
}

/* --------------------------------------------------------------- self-test */

function selfTest() {
  const problems = [];
  const t = (name, cond) => { if (!cond) problems.push(name); };

  const spec = JSON.stringify({
    paths: {
      "/v1/orders": {
        get: { parameters: [{ name: "limit" }], responses: { 200: {}, 400: {} } },
        post: { responses: { 201: {}, 422: {} } },
      },
      "/users": { get: { responses: { 200: {} } } },
      "/v1/getUser": { get: { responses: { 200: {}, 404: {} } } },
      "/v1/Orders/": { get: { parameters: [{ name: "limit" }], responses: { 200: {}, 400: {} } } },
    },
  });
  const ops = parseSpecJson(spec);
  t("spec: parses operations", ops.length === 5);

  const f = checkOperations(ops, { fromSpec: true });
  const rules = (path) => f.filter((x) => x.path === path).map((x) => x.rule);

  t("clean op has no findings", rules("/v1/orders").length === 0);
  t("flags unversioned", rules("/users").includes("unversioned-path"));
  t("flags unpaginated list", rules("/users").includes("unpaginated-list"));
  t("flags undocumented errors", rules("/users").includes("undocumented-errors"));
  t("flags verb in path", rules("/v1/getUser").includes("verb-in-path"));
  t("flags trailing slash", rules("/v1/Orders/").includes("trailing-slash"));
  t("flags mixed case", rules("/v1/Orders/").includes("path-case"));

  // A path parameter must not be mistaken for a verb or break versioning.
  const paramOps = parseSpecJson(JSON.stringify({
    paths: { "/v1/orders/{orderId}": { get: { responses: { 200: {}, 404: {} } } } },
  }));
  t("param path is clean", checkOperations(paramOps, { fromSpec: true }).length === 0);

  // YAML path
  const yaml = [
    "paths:",
    "  /v1/items:",
    "    get:",
    "      parameters:",
    "        - name: cursor",
    "      responses:",
    '        "200":',
    '        "500":',
    "  /legacy:",
    "    get:",
    "      responses:",
    '        "200":',
  ].join("\n");
  const yops = parseSpecYaml(yaml);
  t("yaml: parses operations", yops.length === 2);
  t("yaml: captures params", yops[0].params.includes("cursor"));
  t("yaml: captures responses", yops[0].responses.includes("500"));
  const yf = checkOperations(yops, { fromSpec: true });
  t("yaml: clean op clean", yf.filter((x) => x.path === "/v1/items").length === 0);
  t("yaml: flags legacy", yf.some((x) => x.path === "/legacy" && x.rule === "unversioned-path"));

  // Route scanning across frameworks
  const routes = scanRoutes("x.js", [
    'app.get("/v1/orders", h)',
    'router.post("/v1/createOrder", h)',
  ].join("\n"));
  t("routes: finds both", routes.length === 2);
  t("routes: verb detected", checkOperations(routes, { fromSpec: false }).some((x) => x.rule === "verb-in-path"));

  // Collection detection must not fire on a parameterized path.
  t("collection: plural is a collection", isCollectionPath("/v1/orders"));
  t("collection: param path is not", !isCollectionPath("/v1/orders/{id}"));
  t("collection: singular is not", !isCollectionPath("/v1/health"));

  // Escape hatch
  t("allow: with reason", parseAllow("// api-allow: unversioned-path — internal probe")?.reason === "internal probe");
  t("allow: missing reason flagged", parseAllow("# api-allow: unversioned-path")?.reason === "");

  if (problems.length) {
    console.error("FAIL: api-craft self-test\n  " + problems.join("\n  "));
    return 1;
  }
  console.log("PASS: api-craft self-test");
  return 0;
}

/* -------------------------------------------------------------------- main */

function main() {
  const argv = process.argv.slice(2);

  if (argv.includes("--help") || argv.includes("-h")) {
    console.log(`
api-craft — the contract checker

  node check-api.mjs [paths...]   check the contract (default: .)
  node check-api.mjs --json       machine-readable
  node check-api.mjs --self-test

Rules: unversioned-path, verb-in-path, unpaginated-list, undocumented-errors,
       trailing-slash, path-case

Reads an OpenAPI/Swagger document if present (richest source), otherwise scans
route registrations in source. Reports UNKNOWN and exits 0 when it finds neither.

Escape hatch, on the line or the line above (any comment syntax):
  api-allow: <rule-id> — <reason>
`);
    return 0;
  }

  if (argv.includes("--self-test")) return selfTest();

  const paths = argv.filter((a) => !a.startsWith("--"));
  return run(paths.length ? paths : ["."], { json: argv.includes("--json") });
}

process.exit(main());
