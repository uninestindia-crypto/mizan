# 05 — Dependencies and supply chain

**A dependency is code you did not review, running with your privileges, updated by someone you
have never met** (Law 8). Most applications are mostly third-party code, so most of your attack
surface is code nobody on your team has read.

---

## 1. Before adding one

Ask, every time:

- **Do we need it?** Twenty lines of standard library beats a package with forty transitive
  dependencies. `left-pad` was not an aberration; it was a category.
- **Is it maintained?** Last release, open issue count, more than one maintainer. A single-maintainer
  package is one burnout or one account compromise from being a problem.
- **How much does it drag in?** Check the full transitive tree, not the direct dependency. A
  "small" package pulling ninety others is not small.
- **What privileges does it get?** In most ecosystems, a dependency runs with your full process
  privileges and can read your environment — including your secrets.
- **Could it be typosquatting?** Check the exact name, the download count, and the repository link.
  `reqeusts`, `python3-dateutil`, `crossenv` are real historical attacks.

**Install scripts are the highest-risk feature of any package manager.** They run arbitrary code at
install time, on developer laptops and CI runners, before any of your tests. Where your ecosystem
supports disabling them (`npm ci --ignore-scripts`), consider doing so and allowlisting the few that
genuinely need one.

## 2. Pin everything, commit the lockfile

`project-zero` Law 1. The security-specific reasons:

- **The lockfile pins transitive dependencies too**, which is where a compromise usually enters.
- **Install from the lockfile exactly** in CI — `npm ci`, `poetry install --sync`, `go mod verify`.
  A build that resolves fresh versions can pull a compromised release published an hour ago.
- **Verify integrity hashes.** Modern lockfiles carry them; make sure verification is on.
- **Pin CI actions by commit SHA**, not by tag. Tags move, and an action with repository write
  access is a full compromise. This is a real and repeated attack.

## 3. Audit continuously

- **`npm audit` / `pip-audit` / `cargo audit` / `govulncheck` in CI**, failing the build at `high`
  and above. `project-zero`'s CI asset wires this.
- **Automated update PRs** (Dependabot, Renovate) from day one. Batched weekly minor updates are
  routine; a year of deferred updates is a project nobody schedules.
- **A vulnerability is not automatically exploitable in your context** — check whether you call the
  affected path. But the default is to update; "we assessed it as unreachable" needs to be written
  down, with a date and a re-check.
- **Generate an SBOM** if you ship software to others. When the next widely-exploited CVE lands, the
  only question that matters is "are we affected?", and an SBOM answers it in minutes instead of
  days.

**The realistic risk is not a targeted attack on you. It is a widely-exploited CVE in something you
depend on, disclosed on a Friday, with a working exploit by Saturday.** Speed of update is the
control that matters.

## 4. Keep the surface small

- **Remove dependencies you stopped using.** They still get installed, still run install scripts,
  still carry CVEs.
- **Prefer the standard library**, then a well-maintained single-purpose package, then a framework.
- **One tool per job** — two HTTP clients means two vulnerability surfaces and two update cadences.
- **Vendor or wrap what you barely use.** If you use one function from a large package, consider
  implementing it — `code-craft` §7 on wrapping applies here for security reasons too.

## 5. Base images and runtimes

- **Pin base images by digest** (`@sha256:...`), never by tag. `node:22` moves under you.
- **Use minimal images** — distroless or slim. A shell and a package manager in production are tools
  for an attacker who gets execution.
- **Rebuild regularly** to pick up OS patches. An image built six months ago has six months of
  unpatched CVEs, even if your code has not changed.
- **Scan images** in CI (Trivy, Grype) alongside dependency audit.
- **Run as a non-root user**, with a read-only filesystem where possible.

## 6. Build and release integrity

- **The build runs from a clean checkout** in CI, not from a laptop. A build machine with mutable
  state is a supply-chain risk of your own making.
- **Least privilege for CI.** `permissions: contents: read` by default; grant more only to the job
  that needs it (`project-zero`'s CI asset does this).
- **Guard secrets against untrusted pull requests** — a fork PR that runs with your secrets can
  exfiltrate them in one line.
- **Protect the main branch**: required review, required checks, no force-push.
- **Sign releases and container images** where you distribute them, so consumers can verify
  provenance.

## 7. Internal packages

Your own shared libraries are dependencies too, and they carry an extra failure mode:

- **Dependency confusion**: if an internal package name is unclaimed on the public registry, an
  attacker publishes it there with a higher version and your build silently prefers it. Claim your
  namespaces, or scope internal packages and pin the registry explicitly.
- Version and change internal packages with the same discipline as a public API (`api-craft` Law 4)
  — the consumers are your own teams, and they deploy on their own schedule.

## 8. The practical routine

| Cadence | Action |
|---|---|
| Every PR | Dependency audit + secret scan in CI |
| Weekly | Merge batched minor/patch update PRs |
| Monthly | Review direct dependencies; remove unused ones |
| Quarterly | Major version upgrades, deliberately scheduled |
| On disclosure | Assess and patch; days, not months |
| On offboarding | Revoke registry, CI, and repository access the same day |

**The single highest-value habit is keeping updates small and frequent.** A dependency tree updated
weekly is a routine chore. One updated annually is a migration project that gets postponed —
usually until the disclosure that forces it.
