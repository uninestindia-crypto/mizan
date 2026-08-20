# 01 — Stack selection and version pinning

The stack is the decision with the longest half-life in the project. It is also the one most often
made for the worst reason: because something was new, or because the person choosing wanted to
learn it.

**The governing rule:** you get a small number of innovation tokens. Spend them on the thing that
makes your product different, and spend nothing anywhere else. A novel database in a product whose
value is its scheduling algorithm is a token spent on the wrong problem, and it is paid back in
outages.

---

## 1. The default stack

**Take the default unless you can state, in one sentence, a specific reason it fails this project.**
Write the reason in an ADR. "The team prefers X" is a valid reason if the team is real and will
maintain it. "X is faster" is not, unless you have the benchmark and the requirement.

| Layer | Default | Take something else when |
|---|---|---|
| Language (product code) | **TypeScript**, `strict: true` | CPU-bound core (Go, Rust); heavy ML/data (Python); existing team fluency elsewhere |
| Runtime | **Node LTS**, pinned in `.nvmrc` | Edge-only deploy target; a language choice above dictates otherwise |
| Package manager | **npm** | Monorepo with many packages (pnpm); existing lockfile of another kind |
| Web framework | **The boring default for the language** | You need SSR/routing conventions the default lacks |
| Database | **PostgreSQL** | Genuinely document-shaped and schema-free; or an existing system of record |
| Schema/migrations | **A tool with a real `down`** | Never — this one is not optional (Law 7) |
| Cache / queue | **Nothing, at first** | You have measured the need. Not before. |
| Tests | **One runner for unit + integration**, plus one browser E2E tool | — |
| Hosting | **A managed platform with instant rollback** | Compliance requires otherwise; you have an SRE team |
| CI | **Whatever your host already integrates** | — |

**PostgreSQL is the default for a reason that is not technical taste:** it is the database with the
most answered questions on the internet, which means a weak model, a junior engineer, and a tired
engineer at 3am all get correct answers faster. That property is worth more than most feature
differences.

### The "nothing, at first" row is the important one

Cache, queue, search index, feature-flag service, event bus, microservice split. Each is a real
answer to a real problem you probably do not have yet, and each one doubles the number of ways a
request can fail. Add them when you can name the measurement that forced it.

---

## 2. Choosing when the default does not fit

Score the candidates on these six, in this order. The order matters — a stack that wins on the
last three and loses on the first two is a trap.

| # | Criterion | The question to actually ask |
|---|---|---|
| 1 | **Can we hire/staff it?** | If the person who chose it leaves tomorrow, is the project stuck? |
| 2 | **Are the answers findable?** | Search a real error message from it. Are there answers, or four GitHub issues? |
| 3 | **Is it maintained?** | Commits this quarter, a real release history, more than one maintainer |
| 4 | **Does it fail loudly?** | Type errors at build, not surprises at runtime |
| 5 | **Can we leave?** | What does migrating off cost — a week, or a rewrite? |
| 6 | **Is it fast enough?** | Almost always yes. This is last on purpose. |

**Criterion 5 is the one people skip.** Prefer the boring database and the exotic library over the
reverse: a library is a week to replace, a database is a quarter, and a hosting platform you built
around is a year.

---

## 3. Pinning — Law 1 in practice

"Latest" is not a version. It is a promise to be surprised, usually on a Friday.

| Pin this | With | Committed? |
|---|---|---|
| Language runtime | `.nvmrc`, `.tool-versions`, `requires-python`, `rust-toolchain.toml` | Yes |
| Package manager | `packageManager` field, or the lockfile's own format | Yes |
| Every dependency | The lockfile — `package-lock.json`, `poetry.lock`, `go.sum`, `Cargo.lock` | **Yes, always** |
| Base images | A digest (`@sha256:…`), not a tag — tags move | Yes |
| CI actions | A major version at minimum; a SHA for anything with repo write access | Yes |

**The lockfile is not build noise; it is the difference between two machines building the same
program and two machines building two different programs.** Commit it. In CI install from it
exactly (`npm ci`, `poetry install --sync`) so that a lockfile which disagrees with the manifest
fails the build instead of being silently resolved.

### Dependency hygiene from the first commit

- **Read what you add.** Before a dependency goes in: when was it last released, how many
  maintainers, how many transitive dependencies does it drag in.
- **Prefer the standard library** for anything you could write in twenty lines. `left-pad` was not
  an aberration; it was a category.
- **One tool per job.** Two date libraries, two HTTP clients, or two state managers means every
  future author guesses. Record the winner in the ADR.
- **Automate the updates on day zero** (Dependabot/Renovate). Batched minor updates weekly are
  routine; a year of deferred updates is a project.

---

## 4. Write the ADR

One file, `docs/adr/0001-stack.md`, written the day you choose. The template is in
`founder-mode/references/07-templates.md`; the parts that matter most here:

```markdown
# ADR-0001 — Stack

## Decision
<language, runtime, framework, database, hosting — with exact versions>

## Context
<what the product must do that constrains this>

## Alternatives rejected
<each one, and the ONE sentence reason. This section is the value of the document.>

## Consequences
<what this makes easy, what it makes hard, what it forecloses>

## Revisit when
<the specific, observable trigger — "when p95 write latency exceeds X",
 not "if performance becomes a problem">
```

**"Alternatives rejected" is the section future-you actually needs.** Without it, in six months
somebody re-proposes the thing you already rejected, and nobody remembers why, so the debate
happens twice. With it, the debate takes one minute.

**"Revisit when" prevents the opposite failure** — a decision becoming permanent because nobody
remembers it was conditional. Name the observable trigger.
