#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";

const ALLOWED_ENVIRONMENTS = new Set(["local", "test", "ci"]);
const ALLOWED_RINGS = new Set(["R0", "R1", "R2", "R3", "R4", "R5", "R6"]);
const ALLOWED_SAFETY = new Set(["read-only-check", "test-only"]);
const FULL_REVISION = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i;
const SAFE_ID = /^[a-z0-9][a-z0-9._-]*$/i;
const MAX_OUTPUT_BYTES = 50 * 1024 * 1024;

const REFUSED_COMMANDS = [
  ["destructive filesystem operation", /(?:^|\s)(?:rm\s+-[^\n]*r[^\n]*f|rmdir\s+\/s|remove-item\b[^\n]*-recurse)/i],
  ["destructive Git operation", /\bgit\s+(?:reset\s+--hard|clean\s+-[^\s]*f)/i],
  ["production deployment", /(?:\bvercel\b[^\n]*--prod\b|\bflyctl?\s+deploy\b|\bnetlify\s+deploy\b[^\n]*--prod\b)/i],
  ["cluster mutation", /\b(?:kubectl\s+(?:apply|delete|patch|replace|set)|helm\s+(?:install|upgrade|uninstall)|pulumi\s+up)\b/i],
  ["infrastructure mutation", /\bterraform\s+(?:apply|destroy|import)\b/i],
  ["live database mutation", /\b(?:prisma\s+migrate\s+deploy|supabase\s+db\s+(?:push|reset)|alembic\s+(?:upgrade|downgrade)|dropdb)\b/i],
  ["production flag", /(?:^|\s)--prod(?:uction)?(?:\s|$|=)/i],
];

function fail(message, exitCode = 2) {
  process.stderr.write(`PRELAUNCH CONFIG ERROR: ${message}\n`);
  process.exit(exitCode);
}

function usage() {
  return [
    "Usage:",
    "  node run-prelaunch-gates.mjs --root <repo> --config <json>",
    "  node run-prelaunch-gates.mjs --root <repo> --config <json> --dry-run",
    "  node run-prelaunch-gates.mjs --self-test",
    "",
    "Runs reviewed R0-R6 commands only. It never deploys or clears manual release gates.",
  ].join("\n");
}

function parseArgs(argv) {
  const args = { root: process.cwd(), config: null, dryRun: false, selfTest: false };

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--root") {
      if (!argv[index + 1]) fail("--root requires a value");
      args.root = argv[index + 1];
      index += 1;
    } else if (value === "--config") {
      if (!argv[index + 1]) fail("--config requires a value");
      args.config = argv[index + 1];
      index += 1;
    } else if (value === "--dry-run") {
      args.dryRun = true;
    } else if (value === "--self-test") {
      args.selfTest = true;
    } else if (value === "--help" || value === "-h") {
      process.stdout.write(`${usage()}\n`);
      process.exit(0);
    } else {
      fail(`unknown argument: ${value}`);
    }
  }

  if (!args.selfTest && !args.config) fail("--config is required");
  return args;
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function assertRelativeInside(root, candidate, label) {
  if (typeof candidate !== "string" || candidate.trim() === "") {
    throw new Error(`${label} must be a non-empty relative path`);
  }
  if (path.isAbsolute(candidate)) throw new Error(`${label} must be relative to --root`);

  const resolved = path.resolve(root, candidate);
  const relative = path.relative(root, resolved);
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`${label} resolves outside --root`);
  }
  return resolved;
}

function assertCommandAllowed(command) {
  if (command.includes("\n") || command.includes("\r") || command.includes("\0")) {
    throw new Error("commands must be single-line strings");
  }
  if (/\b(?:authorization|api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+/i.test(command)) {
    throw new Error("command appears to contain an inline credential; use configured environment variables");
  }
  for (const [label, pattern] of REFUSED_COMMANDS) {
    if (pattern.test(command)) throw new Error(`refused ${label}: ${command}`);
  }
}

function validateConfig(config, root) {
  if (!isPlainObject(config)) throw new Error("config must be a JSON object");
  if (config.schemaVersion !== 1) throw new Error("schemaVersion must be 1");
  if (typeof config.release !== "string" || config.release.trim() === "") {
    throw new Error("release must be a non-empty string");
  }
  if (typeof config.revision !== "string" || !FULL_REVISION.test(config.revision)) {
    throw new Error("revision must be a full 40- or 64-character hexadecimal commit identifier");
  }
  if (!ALLOWED_ENVIRONMENTS.has(config.environment)) {
    throw new Error("environment must be local, test, or ci; production and staging are refused");
  }
  if (config.requireCleanTree !== true) {
    throw new Error("requireCleanTree must be true for release evidence");
  }

  const evidencePath = assertRelativeInside(root, config.evidencePath, "evidencePath");
  if (!Array.isArray(config.gates) || config.gates.length === 0) {
    throw new Error("gates must contain at least one automated gate");
  }

  const ids = new Set();
  const gates = config.gates.map((gate, index) => {
    const prefix = `gates[${index}]`;
    if (!isPlainObject(gate)) throw new Error(`${prefix} must be an object`);
    if (typeof gate.id !== "string" || !SAFE_ID.test(gate.id)) {
      throw new Error(`${prefix}.id must contain only letters, digits, dots, underscores, and hyphens`);
    }
    if (ids.has(gate.id)) throw new Error(`${prefix}.id is duplicated: ${gate.id}`);
    ids.add(gate.id);
    if (!ALLOWED_RINGS.has(gate.ring)) throw new Error(`${prefix}.ring must be R0 through R6`);
    if (typeof gate.name !== "string" || gate.name.trim() === "") {
      throw new Error(`${prefix}.name must be a non-empty string`);
    }
    if (typeof gate.command !== "string" || gate.command.trim() === "") {
      throw new Error(`${prefix}.command must be a non-empty string`);
    }
    assertCommandAllowed(gate.command);
    if (!ALLOWED_SAFETY.has(gate.safety)) {
      throw new Error(`${prefix}.safety must be read-only-check or test-only`);
    }
    if (gate.required !== true) {
      throw new Error(`${prefix}.required must be true; record non-applicable gates in PRELAUNCH.md`);
    }
    if (!Number.isInteger(gate.timeoutSeconds) || gate.timeoutSeconds < 1 || gate.timeoutSeconds > 7200) {
      throw new Error(`${prefix}.timeoutSeconds must be an integer from 1 to 7200`);
    }

    return {
      ...gate,
      resolvedCwd: assertRelativeInside(root, gate.cwd, `${prefix}.cwd`),
    };
  });

  return { ...config, evidencePath, gates };
}

function redact(value) {
  return String(value ?? "")
    .replace(/\b(Bearer)\s+[A-Za-z0-9._~+/=-]+/gi, "$1 [REDACTED]")
    .replace(/((?:authorization|api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*)\S+/gi, "$1[REDACTED]");
}

function runProcess(command, options = {}) {
  const started = Date.now();
  const result = spawnSync(command, {
    cwd: options.cwd,
    shell: true,
    encoding: "utf8",
    timeout: options.timeoutSeconds ? options.timeoutSeconds * 1000 : undefined,
    maxBuffer: MAX_OUTPUT_BYTES,
    windowsHide: true,
  });
  return { ...result, durationMs: Date.now() - started };
}

function gitOutput(root, args) {
  return spawnSync("git", args, {
    cwd: root,
    shell: false,
    encoding: "utf8",
    timeout: 30_000,
    maxBuffer: MAX_OUTPUT_BYTES,
    windowsHide: true,
  });
}

function requireGitSuccess(result, action) {
  if (result.status !== 0) {
    throw new Error(`${action}: ${redact(result.stderr || result.error?.message || "unknown Git error")}`);
  }
}

function verifyRevisionAndTree(root, config, configPath) {
  const topResult = gitOutput(root, ["rev-parse", "--show-toplevel"]);
  requireGitSuccess(topResult, "cannot resolve repository root");
  if (path.resolve(topResult.stdout.trim()).toLowerCase() !== root.toLowerCase()) {
    throw new Error("--root must be the Git repository root");
  }

  const headResult = gitOutput(root, ["rev-parse", "--verify", "HEAD"]);
  requireGitSuccess(headResult, "cannot resolve git HEAD");
  const head = headResult.stdout.trim().toLowerCase();
  if (head !== config.revision.toLowerCase()) {
    throw new Error(`config revision ${config.revision} does not match HEAD ${head}`);
  }

  const unstagedResult = gitOutput(root, ["diff", "--quiet", "--exit-code"]);
  if (unstagedResult.status !== 0) throw new Error("working tree has tracked unstaged changes");
  const stagedResult = gitOutput(root, ["diff", "--cached", "--quiet", "--exit-code"]);
  if (stagedResult.status !== 0) throw new Error("working tree has staged changes");

  const untrackedResult = gitOutput(root, ["ls-files", "--others", "--exclude-standard", "-z"]);
  requireGitSuccess(untrackedResult, "cannot inspect untracked files");
  const configRelative = path.relative(root, configPath).replaceAll("\\", "/");
  const untracked = untrackedResult.stdout.split("\0").filter(Boolean);
  const productUntracked = untracked.filter((entry) => entry !== configRelative);
  if (productUntracked.length > 0) {
    throw new Error(`working tree has untracked files other than the release config: ${productUntracked.slice(0, 5).join(", ")}`);
  }
  return head;
}

function indentRaw(value) {
  const safe = redact(value).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  return safe === "" ? "    <empty>" : safe.split("\n").map((line) => `    ${line}`).join("\n");
}

function writeEvidence(filePath, state) {
  const lines = [
    "# Automated pre-launch evidence",
    "",
    `Release: ${state.release}`,
    `Revision: ${state.revision}`,
    `Config SHA-256: ${state.configDigest}`,
    `Environment: ${state.environment}`,
    `Started: ${state.started}`,
    `Completed: ${state.completed ?? "in progress"}`,
    `Verdict: ${state.verdict}`,
    "",
  ];

  for (const result of state.results) {
    lines.push(
      `## ${result.ring} - ${result.name}`,
      "",
      `Gate: ${result.id}`,
      `Command: ${redact(result.command)}`,
      `Working directory: ${result.cwd}`,
      `Exit status: ${result.status ?? "no exit status"}`,
      `Duration: ${result.durationMs} ms`,
      `Verdict: ${result.verdict}`,
      "",
      "### stdout",
      "",
      indentRaw(result.stdout),
      "",
      "### stderr",
      "",
      indentRaw(result.stderr || result.error || ""),
      "",
    );
  }

  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${lines.join("\n")}\n`, { encoding: "utf8", flag: "wx" });
}

function runSelfTest() {
  const root = process.cwd();
  const sample = {
    schemaVersion: 1,
    release: "self-test",
    revision: "0123456789abcdef0123456789abcdef01234567",
    environment: "test",
    requireCleanTree: true,
    evidencePath: ".launch/evidence/self-test.md",
    gates: [{
      id: "r0-self-test",
      ring: "R0",
      name: "Self test",
      command: `\"${process.execPath}\" -e \"process.exit(0)\"`,
      cwd: ".",
      safety: "read-only-check",
      required: true,
      timeoutSeconds: 10,
    }],
  };

  const validated = validateConfig(sample, root);
  if (validated.gates.length !== 1) throw new Error("valid config was not accepted");
  const passing = runProcess(sample.gates[0].command, { cwd: root, timeoutSeconds: 10 });
  if (passing.status !== 0) throw new Error("passing command did not pass");
  const failing = runProcess(`\"${process.execPath}\" -e \"process.exit(7)\"`, { cwd: root, timeoutSeconds: 10 });
  if (failing.status !== 7) throw new Error("failing command did not preserve its exit status");
  if (!redact("Authorization: Bearer abc123").includes("[REDACTED]")) {
    throw new Error("redaction self-test failed");
  }
  let refused = false;
  try {
    assertCommandAllowed("terraform apply");
  } catch {
    refused = true;
  }
  if (!refused) throw new Error("stateful command self-test failed");
  process.stdout.write("PASS: pre-launch runner self-test\n");
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.selfTest) {
    runSelfTest();
    return;
  }

  const root = path.resolve(args.root);
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) fail(`root is not a directory: ${root}`);

  let configPath;
  let configText;
  let config;
  let head;
  try {
    configPath = assertRelativeInside(root, args.config, "config path");
    if (!fs.existsSync(configPath)) throw new Error(`config does not exist: ${configPath}`);
    configText = fs.readFileSync(configPath, "utf8");
    config = validateConfig(JSON.parse(configText), root);
    if (fs.existsSync(config.evidencePath)) {
      throw new Error(`evidence path already exists; preserve it and choose a new path: ${config.evidencePath}`);
    }
    head = verifyRevisionAndTree(root, config, configPath);
  } catch (error) {
    fail(redact(error.message));
  }

  if (args.dryRun) {
    process.stdout.write(`VALID: ${config.gates.length} gates for ${config.release} at ${head}\n`);
    for (const gate of config.gates) process.stdout.write(`  ${gate.ring} ${gate.id}: ${gate.command}\n`);
    return;
  }

  const state = {
    release: config.release,
    revision: head,
    configDigest: crypto.createHash("sha256").update(configText).digest("hex"),
    environment: config.environment,
    started: new Date().toISOString(),
    completed: null,
    verdict: "RUNNING",
    results: [],
  };

  for (const gate of config.gates) {
    process.stdout.write(`RUN ${gate.ring} ${gate.id}: ${gate.name}\n`);
    const result = runProcess(gate.command, {
      cwd: gate.resolvedCwd,
      timeoutSeconds: gate.timeoutSeconds,
    });
    const passed = result.status === 0 && !result.error;
    state.results.push({
      id: gate.id,
      ring: gate.ring,
      name: gate.name,
      command: gate.command,
      cwd: path.relative(root, gate.resolvedCwd) || ".",
      status: result.status,
      durationMs: result.durationMs,
      verdict: passed ? "PASS" : "BLOCKED",
      stdout: result.stdout,
      stderr: result.stderr,
      error: result.error?.message,
    });

    if (!passed) {
      state.completed = new Date().toISOString();
      state.verdict = "BLOCKED";
      writeEvidence(config.evidencePath, state);
      process.stderr.write(`BLOCKED at ${gate.id}; evidence: ${config.evidencePath}\n`);
      process.exit(1);
    }
  }

  state.completed = new Date().toISOString();
  state.verdict = "PASS - AUTOMATED R0-R6 ONLY";
  writeEvidence(config.evidencePath, state);
  process.stdout.write(`PASS: automated gates only; manual steps 1-2 and 11-15 remain. Evidence: ${config.evidencePath}\n`);
}

try {
  main();
} catch (error) {
  fail(redact(error?.stack || error?.message || error));
}
