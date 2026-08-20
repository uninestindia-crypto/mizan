#!/usr/bin/env node
/**
 * SECURE BY DEFAULT — THE SCANNER
 *
 * Zero dependencies. Node 18+.
 *
 *   node check-security.mjs [paths...]   scan (default: .)
 *   node check-security.mjs --json       machine-readable
 *   node check-security.mjs --rules      list the rules
 *   node check-security.mjs --self-test
 *
 * EXIT CODES
 *   0  clean
 *   1  findings
 *   2  bad usage
 *
 * ESCAPE HATCH, on the offending line or the line above it:
 *   sec-allow: <rule-id> — <reason>
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT THIS IS
 *
 * A DEFENSIVE build-time check on your own source. It looks for the small set of
 * mistakes behind most real incidents: a credential in the repository, a query
 * built by concatenation, TLS verification switched off during debugging and
 * never switched back, a fast hash used for passwords, and deserialization of
 * untrusted data.
 *
 * WHAT IT IS NOT
 * Not a substitute for a dependency audit, a history-aware secret scanner, or a
 * professional assessment. It sees the current working tree only — a secret
 * committed and later deleted is still in the history and still compromised.
 *
 * WHAT IT DELIBERATELY CANNOT CHECK
 * Whether an authorization rule is correct, whether a tenant boundary holds,
 * whether the data model over-collects. Those need a threat model and judgment.
 * A scanner that pretends to have judgment produces confident wrong answers and
 * a false sense of safety, which is worse than no scanner.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, basename, join, relative, resolve } from "node:path";

/* ------------------------------------------------------------------ config */

const SKIP_DIR = new Set([
  "node_modules", ".git", "dist", "build", ".next", ".nuxt", "out", "coverage",
  "vendor", ".turbo", ".cache", "target", "__pycache__", ".venv", "venv",
  "test", "tests", "spec", "__tests__", "fixtures", "testdata", "examples",
]);

const SCAN_EXT = new Set([
  ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".py", ".go", ".rb", ".php",
  ".java", ".kt", ".cs", ".rs", ".scala", ".sh", ".bash", ".yml", ".yaml",
  ".json", ".env", ".tf", ".properties", ".ini", ".xml", ".config",
]);

const COMMENT = ["//", "#", "--", ";", "*"];
const isComment = (l) => { const t = l.trimStart(); return COMMENT.some((c) => t.startsWith(c)); };

/** Values that are obviously placeholders, not real credentials. */
const PLACEHOLDER = /^(x{3,}|\.{3,}|\*{3,}|<[^>]+>|\$\{[^}]+\}|%\([^)]+\)s|\{\{[^}]+\}\}|change[_-]?me|your[_-]?\w+|example|sample|dummy|test|placeholder|redacted|none|null|nil|undefined|foo|bar|secret|password|todo|tbd|insert[_-]?\w+|my[_-]?\w+|abc123|password123|env\.\w+|process\.env\.\w+|os\.environ.*)$/i;

/* -------------------------------------------------------------------- rules */

const RULES = [
  {
    id: "hardcoded-credential",
    severity: "critical",
    why: "A credential in source is compromised the moment it is pushed — and it stays in the history after deletion. Move it to the config contract and ROTATE the value.",
    test: (line) => {
      // key-ish name, then an assignment, then a non-placeholder literal
      const m = /\b(pass(?:word|wd)?|secret|api[_-]?key|apikey|auth[_-]?token|access[_-]?token|private[_-]?key|client[_-]?secret|encryption[_-]?key)\b\s*[:=]\s*["'`]([^"'`\n]{6,})["'`]/i.exec(line);
      if (!m) return false;
      const value = m[2].trim();
      if (PLACEHOLDER.test(value)) return false;
      if (/^\$\{|^process\.env|^os\.environ|^env\[|^ENV\[|^config\./i.test(value)) return false;
      return true;
    },
  },
  {
    id: "private-key-material",
    severity: "critical",
    why: "Private key material in the repository. Revoke and reissue the key — deleting the file does not remove it from the history.",
    test: (line) => /-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----/.test(line),
  },
  {
    id: "known-token-format",
    severity: "critical",
    why: "A live-looking provider token. Revoke it now, then move it to the config contract.",
    test: (line) =>
      /\b(sk_live_[A-Za-z0-9]{16,}|rk_live_[A-Za-z0-9]{16,})\b/.test(line) ||   // Stripe live
      /\bgh[pousr]_[A-Za-z0-9]{30,}\b/.test(line) ||                             // GitHub
      /\bxox[abps]-[A-Za-z0-9-]{10,}\b/.test(line) ||                            // Slack
      /\bAKIA[0-9A-Z]{16}\b/.test(line) ||                                       // AWS access key id
      /\bAIza[0-9A-Za-z_-]{35}\b/.test(line),                                    // Google API key
  },
  {
    id: "sql-string-building",
    severity: "critical",
    why: "Law 3: a query built by concatenation or interpolation is an injection. Use parameterized queries — every driver has them.",
    test: (line) => {
      if (!/\b(select|insert|update|delete|drop|where|from|into|values)\b/i.test(line)) return false;
      // interpolation inside a query string, or concatenation of a query fragment
      return (
        /["'`][^"'`]*\b(select|insert|update|delete)\b[^"'`]*["'`]\s*[+.]\s*\w/i.test(line) ||
        /`[^`]*\$\{[^}]+\}[^`]*`/.test(line) && /\b(select|insert|update|delete|where)\b/i.test(line) ||
        /f["'][^"']*\{[^}]+\}[^"']*["']/.test(line) && /\b(select|insert|update|delete|where)\b/i.test(line) ||
        /%\s*\(?\s*\w+\s*\)?\s*[,)]/.test(line) && /\bexecute\s*\(/i.test(line) && /%s/.test(line) === false
      );
    },
  },
  {
    id: "command-injection",
    severity: "critical",
    why: "A shell command built from a variable. Pass an argument array instead, and never enable a shell for untrusted input.",
    test: (line) =>
      (/\b(exec|execSync|system|popen|spawnSync|shell_exec|passthru)\s*\(/.test(line) &&
        /[`"'][^`"']*\$\{|["'][^"']*["']\s*\+\s*\w|f["'][^"']*\{/.test(line)) ||
      /\bsubprocess\.\w+\([^)]*shell\s*=\s*True/.test(line) ||
      /\bos\.system\s*\(/.test(line),
  },
  {
    id: "tls-verification-disabled",
    severity: "critical",
    why: "TLS verification is off, so any network position can read and modify this traffic. Almost always left over from debugging.",
    test: (line) =>
      /rejectUnauthorized\s*:\s*false/.test(line) ||
      /\bverify\s*=\s*False\b/.test(line) ||
      /InsecureSkipVerify\s*:\s*true/.test(line) ||
      /NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*["']?0/.test(line) ||
      /ServicePointManager\.ServerCertificateValidationCallback\s*\+?=\s*.*true/.test(line) ||
      /\bcurl\b.*\s(-k|--insecure)\b/.test(line),
  },
  {
    id: "weak-password-hash",
    severity: "high",
    why: "MD5/SHA-1/SHA-256 are fast by design, which is exactly wrong for passwords. Use bcrypt, scrypt, or Argon2 with the library's defaults.",
    test: (line) =>
      /\b(md5|sha1|sha256)\s*\(\s*[^)]*\b(pass(word|wd)?|pwd|secret|credential)\b/i.test(line) ||
      /\b(pass(word|wd)?|pwd)\b[^=\n]*=\s*\w*\b(md5|sha1)\s*\(/i.test(line),
  },
  {
    id: "unsafe-deserialization",
    severity: "critical",
    why: "Deserializing untrusted data executes attacker-chosen code. Use JSON, or a schema-validated format.",
    test: (line) =>
      /\bpickle\.loads?\s*\(/.test(line) ||
      /\byaml\.load\s*\((?![^)]*Loader\s*=\s*(?:yaml\.)?SafeLoader)/.test(line) ||
      /\bObjectInputStream\s*\(/.test(line) ||
      /\bunserialize\s*\(/.test(line) ||
      /\bMarshal\.load\s*\(/.test(line),
  },
  {
    id: "dangerous-eval",
    severity: "high",
    why: "Evaluating a string built at runtime is arbitrary code execution if any part of it is influenced by input.",
    test: (line) =>
      /\beval\s*\(/.test(line) ||
      /\bnew\s+Function\s*\(/.test(line) ||
      /\bexec\s*\(\s*["'`]/.test(line) && /\.py$|python/i.test("") === false && /\bexec\s*\(/.test(line) && /\$\{|\+\s*\w/.test(line),
  },
  {
    id: "markup-injection",
    severity: "high",
    why: "Assigning unescaped content to raw markup is cross-site scripting. Use text assignment, or the framework's escaping.",
    test: (line) => {
      /* Extract the right-hand side and judge it directly. A negative lookahead
         cannot be used here: the `\s*` before it backtracks to zero width, the
         lookahead then sees a space instead of a quote, and the rule fires on
         the safe `innerHTML = ""` clear. */
      const assign = /\.innerHTML\s*=\s*(.*)$/.exec(line);
      if (assign) {
        const rhs = assign[1].trim();
        const isEmptyLiteral = /^(["'`])\s*\1\s*;?$/.test(rhs);
        if (!isEmptyLiteral) return true;
      }
      return (
        /dangerouslySetInnerHTML/.test(line) ||
        /\bv-html\b/.test(line) ||
        /\|\s*safe\b/.test(line) ||
        /\bmark_safe\s*\(/.test(line)
      );
    },
  },
  {
    id: "path-traversal",
    severity: "high",
    why: "A filesystem path built from input can escape its directory with `../`. Resolve the path, then assert it is still inside the intended root.",
    test: (line) =>
      /(readFile|writeFile|open|sendFile|createReadStream|File)\s*\(\s*[^)]*(\bpath\.join\s*\([^)]*(req\.|request\.|params|query|body|argv)|["'`][^"'`]*["'`]\s*\+\s*(req\.|request\.|params|query|body))/.test(line),
  },
  {
    id: "permissive-cors",
    severity: "high",
    why: "A wildcard origin with credentials lets any site make authenticated requests as your user. Name the allowed origins.",
    test: (line) =>
      /Access-Control-Allow-Origin["']?\s*[:,]\s*["']\*/.test(line) ||
      /\borigin\s*:\s*["']\*["']/.test(line) ||
      /\bcors\s*\(\s*\{[^}]*origin\s*:\s*true/.test(line),
  },
  {
    id: "insecure-random",
    severity: "high",
    why: "A predictable generator used for a token or key. Use the platform's cryptographic random source.",
    test: (line) =>
      /\b(Math\.random|random\.random|rand\.Intn|mt_rand|new Random\s*\()\s*\(?/.test(line) &&
      /\b(token|secret|key|nonce|salt|otp|session|password|reset|csrf)\b/i.test(line),
  },
];

/* ------------------------------------------------------------------ engine */

function parseAllow(line) {
  const m = /sec-allow:\s*([a-z0-9-]+?)\s+[—–-]\s+(.+?)\s*(?:\*\/|-->|$)/.exec(line);
  if (m) return { id: m[1], reason: m[2].trim() };
  const bare = /sec-allow:\s*([a-z0-9-]+)/.exec(line);
  if (bare) return { id: bare[1], reason: "" };
  return null;
}

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

const read = (p) => { try { return readFileSync(p, "utf8"); } catch { return ""; } };

function scanFile(path, root) {
  const ext = extname(path);
  const name = basename(path);
  // .env files have no extension pattern but are exactly what we care about.
  if (!SCAN_EXT.has(ext) && !/^\.env(\..+)?$/.test(name)) return null;

  const text = read(path);
  if (!text) return null;
  const lines = text.split(/\r?\n/);
  const rel = relative(root, path) || path;
  const out = [];

  lines.forEach((raw, i) => {
    if (!raw.trim()) return;
    const n = i + 1;
    const here = parseAllow(raw);
    const above = parseAllow(lines[i - 1] ?? "");

    if (here && here.reason === "") {
      out.push({ file: rel, line: n, rule: "unexplained-escape", severity: "medium",
        why: "An escape with no stated reason is a risk someone hid. Write why after an em dash." });
    }

    // Comments can still hold a real pasted credential, so the secret rules run
    // on them; the code-shape rules do not.
    const commentLine = isComment(raw);

    for (const rule of RULES) {
      if (commentLine && !/credential|key|token/.test(rule.id)) continue;
      if ((here && here.id === rule.id) || (above && above.id === rule.id)) continue;
      if (rule.test(raw)) {
        out.push({ file: rel, line: n, rule: rule.id, severity: rule.severity, why: rule.why });
      }
    }
  });

  return { rel, findings: out };
}

const ORDER = { critical: 0, high: 1, medium: 2 };

function run(targets, { json = false } = {}) {
  const root = process.cwd();
  const files = targets.flatMap((t) => collect(resolve(t)));
  const all = [];
  let scanned = 0;

  for (const f of files) {
    const r = scanFile(f, root);
    if (!r) continue;
    scanned++;
    all.push(...r.findings);
  }

  if (json) {
    console.log(JSON.stringify({ scanned, findings: all }, null, 2));
    return all.length ? 1 : 0;
  }

  if (scanned === 0) {
    console.log("secure-by-default: UNKNOWN — no scannable files found.");
    return 0;
  }
  if (all.length === 0) {
    console.log(`secure-by-default: clean — ${scanned} file(s) scanned.`);
    console.log(`  This checks the working tree only. Pair it with a dependency audit and a`);
    console.log(`  history-aware secret scanner — a deleted secret is still in the history.`);
    return 0;
  }

  all.sort((a, b) => (ORDER[a.severity] - ORDER[b.severity]) || a.file.localeCompare(b.file) || a.line - b.line);

  let lastFile = null;
  for (const f of all) {
    if (f.file !== lastFile) { console.log(`\n${f.file}`); lastFile = f.file; }
    console.log(`  ${String(f.line).padStart(5)}:  [${f.severity.toUpperCase()}] ${f.rule}`);
    console.log(`         ${f.why}`);
  }

  const bySeverity = new Map();
  for (const f of all) bySeverity.set(f.severity, (bySeverity.get(f.severity) ?? 0) + 1);

  console.log(`\n${"-".repeat(76)}`);
  console.log(`secure-by-default: ${all.length} finding(s) in ${scanned} file(s) scanned.`);
  for (const s of ["critical", "high", "medium"]) {
    if (bySeverity.has(s)) console.log(`  ${String(bySeverity.get(s)).padStart(4)}  ${s}`);
  }
  if (bySeverity.has("critical")) {
    console.log(`\n  Any credential finding means ROTATE THE VALUE, not just delete the line —`);
    console.log(`  it is in the history, and the history is on every clone.`);
  }
  console.log(`\nFix them, or annotate the genuinely-correct ones:  sec-allow: <rule-id> — <reason>`);
  return 1;
}

/* --------------------------------------------------------------- self-test */

function selfTest() {
  const problems = [];
  const t = (name, cond) => { if (!cond) problems.push(name); };
  const fire = (id, line) => RULES.find((r) => r.id === id).test(line);

  // Credentials — must fire on real values, stay silent on placeholders/config.
  t("cred: real value", fire("hardcoded-credential", 'const apiKey = "sk_live_9fJq2mNvWx7Lp0Rt"'));
  t("cred: password literal", fire("hardcoded-credential", 'password = "hunter2correct"'));
  t("cred: ignores env ref", !fire("hardcoded-credential", 'const apiKey = process.env.API_KEY'));
  t("cred: ignores placeholder", !fire("hardcoded-credential", 'password = "changeme"'));
  t("cred: ignores template", !fire("hardcoded-credential", 'api_key = "${API_KEY}"'));
  t("cred: ignores empty-ish", !fire("hardcoded-credential", 'password = "xxx"'));

  t("token: aws", fire("known-token-format", 'AKIAIOSFODNN7EXAMPLE'));
  t("token: github", fire("known-token-format", 'ghp_16CharactersLongToken000000000000000'));
  t("key: pem", fire("private-key-material", "-----BEGIN RSA PRIVATE KEY-----"));

  // Injection
  t("sql: template literal", fire("sql-string-building", 'db.query(`SELECT * FROM users WHERE id = ${id}`)'));
  t("sql: concatenation", fire("sql-string-building", 'db.query("SELECT * FROM users WHERE id = " + id)'));
  t("sql: python f-string", fire("sql-string-building", 'cur.execute(f"SELECT * FROM t WHERE id = {uid}")'));
  t("sql: ignores parameterized", !fire("sql-string-building", 'db.query("SELECT * FROM users WHERE id = $1", [id])'));
  t("sql: ignores prose", !fire("sql-string-building", 'const label = "Delete from list"'));

  t("cmd: shell=True", fire("command-injection", 'subprocess.run(cmd, shell=True)'));
  t("cmd: os.system", fire("command-injection", 'os.system("ls " + path)'));
  t("cmd: template exec", fire("command-injection", 'execSync(`git checkout ${branch}`)'));

  // TLS
  t("tls: node", fire("tls-verification-disabled", "rejectUnauthorized: false"));
  t("tls: python", fire("tls-verification-disabled", "requests.get(url, verify=False)"));
  t("tls: go", fire("tls-verification-disabled", "InsecureSkipVerify: true"));

  // Hashing and deserialization
  t("hash: md5 password", fire("weak-password-hash", 'const h = md5(password)'));
  t("hash: ignores md5 etag", !fire("weak-password-hash", 'const etag = md5(fileBuffer)'));
  t("deser: pickle", fire("unsafe-deserialization", "data = pickle.loads(blob)"));
  t("deser: yaml unsafe", fire("unsafe-deserialization", "cfg = yaml.load(text)"));
  t("deser: yaml safe ok", !fire("unsafe-deserialization", "cfg = yaml.load(text, Loader=yaml.SafeLoader)"));

  // Web surface
  t("xss: innerHTML", fire("markup-injection", "el.innerHTML = userInput"));
  t("xss: ignores empty", !fire("markup-injection", 'el.innerHTML = ""'));
  t("cors: wildcard", fire("permissive-cors", "'Access-Control-Allow-Origin': '*'"));
  t("rand: token", fire("insecure-random", "const token = Math.random().toString(36)"));
  t("rand: ignores non-security", !fire("insecure-random", "const jitter = Math.random() * 100"));

  // Escape hatch
  t("allow: with reason", parseAllow("// sec-allow: permissive-cors — public read-only CDN")?.reason === "public read-only CDN");
  t("allow: missing reason", parseAllow("# sec-allow: hardcoded-credential")?.reason === "");

  // Every rule must be well formed and survive an ordinary line.
  for (const r of RULES) {
    if (!r.id || !r.why || !r.severity) problems.push(`rule ${r.id} malformed`);
    if (!ORDER[r.severity]) if (r.severity !== "critical") problems.push(`rule ${r.id} bad severity`);
    try { r.test("const x = 1;"); } catch { problems.push(`rule ${r.id} throws on a plain line`); }
  }

  if (problems.length) {
    console.error("FAIL: secure-by-default self-test\n  " + problems.join("\n  "));
    return 1;
  }
  console.log(`PASS: secure-by-default self-test (${RULES.length} rules)`);
  return 0;
}

/* -------------------------------------------------------------------- main */

function main() {
  const argv = process.argv.slice(2);

  if (argv.includes("--help") || argv.includes("-h")) {
    console.log(`
secure-by-default — the defensive scanner

  node check-security.mjs [paths...]   scan (default: .)
  node check-security.mjs --json       machine-readable
  node check-security.mjs --rules      list the rules
  node check-security.mjs --self-test

Escape hatch, on the line or the line above (any comment syntax):
  sec-allow: <rule-id> — <reason>

Scans the working tree only. Pair with a dependency audit and a history-aware
secret scanner: a secret committed and later deleted is still in the history.
`);
    return 0;
  }

  if (argv.includes("--self-test")) return selfTest();

  if (argv.includes("--rules")) {
    console.log("Rules:\n");
    for (const s of ["critical", "high"]) {
      for (const r of RULES.filter((x) => x.severity === s)) {
        console.log(`  [${s.toUpperCase().padEnd(8)}] ${r.id}`);
        console.log(`              ${r.why}\n`);
      }
    }
    return 0;
  }

  const paths = argv.filter((a) => !a.startsWith("--"));
  return run(paths.length ? paths : ["."], { json: argv.includes("--json") });
}

process.exit(main());
