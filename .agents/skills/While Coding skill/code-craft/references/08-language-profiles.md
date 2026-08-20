# 08 — Language profiles

**The ten laws are language-neutral. Their expression is not.**

"Name things clearly" is universal. Whether that name is `user_count`, `userCount`, or `UserCount`
is not — and getting it wrong makes correct code look foreign in its own repository, which is its
own kind of defect.

A profile is one short section per language, at `docs/code-profile.md`. Write it once. Where the
language has a dominant community standard, the profile is mostly a pointer to it, which takes two
minutes and settles a hundred future arguments.

---

## The rule that outranks everything in this skill

**The language's own idiom wins. Then the project's existing code wins. Then this skill.**

Writing Go with try/catch-shaped error handling, or Python with camelCase, produces code that is
technically compliant with the laws and wrong for its readers. A law that fights the language has
been misapplied — the law is about the reader, and the reader knows the language.

When this skill and the language's idiom genuinely conflict, the idiom wins and you note it in the
profile. That is what the profile is for.

---

## The template

```markdown
# CODE PROFILE — <project>

## Product type
<library | service | CLI | data pipeline | embedded | game | UI app>
See references/07-product-types.md for what this tightens.

## Languages
<list, with what each is used for>

---

## <Language> — e.g. Python 3.12

Style authority:     <PEP 8 + the formatter; "the formatter is the bar, not review">
Formatter:           <black / ruff format / gofmt / rustfmt / prettier>   — command:
Linter:              <ruff / golangci-lint / clippy / eslint>             — command:
Typechecker:         <mypy / pyright / tsc / none>                        — command:

Naming:
  functions/vars     <snake_case>
  types/classes      <PascalCase>
  constants          <UPPER_SNAKE>
  private/internal   <_leading_underscore | unexported lowercase | private keyword>
  files/modules      <snake_case.py>

Errors:
  signalled by       <exceptions | (value, err) tuple | Result<T,E> | error return>
  the base type      <the project's own error base, if any>
  never              <the anti-pattern for this language, e.g. bare `except:`>

Modules:
  unit of boundary   <package | module | crate | namespace>
  visibility default <public unless marked | private unless exported>
  cycle check        <the command that detects import cycles>

Testing:
  framework          <pytest / go test / cargo test / vitest>
  file convention    <test_*.py / *_test.go / *.test.ts>

Thresholds (override the checker defaults, with the reason):
  maxFunctionLines   <e.g. 60 — this codebase's handlers are legitimately longer>
  maxNesting         <e.g. 3>

Idiom notes — where this language overrides the skill:
  - <e.g. "Go: `if err != nil { return err }` at every call is idiomatic, not noise.
     Law 3's nesting budget does not count these guards.">
```

---

## Worked example

```markdown
# CODE PROFILE — Orbit (order management)

## Product type
Service (HTTP API) + one CLI for operators.
Tightens: failure handling, idempotency, timeouts, observability, exit codes.

## Languages
Go — the API service and the CLI
Python — the nightly reconciliation job
SQL — migrations and reports

---

## Go 1.23

Style authority:     Effective Go + gofmt. Formatting is never a review comment.
Formatter:           gofmt -l .            (CI fails on any output)
Linter:              golangci-lint run
Typechecker:         the compiler

Naming:
  functions/vars     camelCase; exported PascalCase
  types              PascalCase
  constants          camelCase or PascalCase — Go does not use UPPER_SNAKE
  private/internal   lowercase first letter; `internal/` package for hard privacy
  files              lower_snake.go, _test.go suffix for tests

Errors:
  signalled by       error return values, always the last return
  the base type      wrap with fmt.Errorf("%w") to preserve the chain
  never              panic in library code; _ = err to discard silently

Modules:
  unit of boundary   package
  visibility default private unless the identifier is capitalized
  cycle check        the compiler forbids them outright

Testing:
  framework          go test, table-driven
  file convention    *_test.go beside the code

Thresholds:
  maxFunctionLines   50 (default)
  maxNesting         3, NOT counting `if err != nil` guards — see idiom note

Idiom notes:
  - `if err != nil { return nil, err }` after every call is correct Go and is not
    "deep nesting". It is the language's error propagation, and flattening it into
    something cleverer makes the code worse. Annotate a genuine false positive:
        // craft-allow: deep-nesting — sequential error guards, idiomatic Go
  - Accept interfaces, return structs.
  - Context is the first parameter and is never stored in a struct.

---

## Python 3.12

Style authority:     PEP 8 via ruff. Formatting is never a review comment.
Formatter:           ruff format .
Linter:              ruff check .
Typechecker:         mypy --strict src/

Naming:
  functions/vars     snake_case
  types/classes      PascalCase
  constants          UPPER_SNAKE
  private            _leading_underscore
  files              snake_case.py

Errors:
  signalled by       exceptions, from a project base class
  the base type      OrbitError, subclassed per failure kind
  never              bare `except:` — it swallows KeyboardInterrupt and SystemExit

Modules:
  unit of boundary   package (directory with __init__.py)
  visibility default public; _prefix signals internal
  cycle check        ruff's import rules + a startup import test

Testing:
  framework          pytest
  file convention    test_*.py under tests/

Thresholds:
  maxFunctionLines   50 (default)
  maxNesting         3 (default)

Idiom notes:
  - Comprehensions over map/filter, but never a nested comprehension — that is
    a loop wearing a disguise, and Law 3 applies to it.
  - Prefer dataclasses over dicts for anything with a fixed shape (Law 4).
  - EAFP over LBYL where it is genuinely idiomatic, but never as a reason to
    write a bare except.
```

---

## Filling it in — the parts people get wrong

**"The formatter is the bar" is the highest-value line in the file.** Once a formatter runs in CI,
formatting stops being a review topic forever. Every minute spent on brace placement in a pull
request is a minute not spent on whether the code is correct. Settle it mechanically on day one.

**Thresholds need a reason, not just a number.** `maxFunctionLines: 120` with no explanation is
someone silencing the checker. With "our request handlers are table-driven and legitimately long"
it is a considered decision, and the next person can evaluate it.

**The idiom notes section is what makes this skill portable.** It is where you record that Go's
error guards are not nesting, that Rust's `?` is not hidden control flow, that a Python decorator
stack is not indirection. Without it, a generic law gets applied by someone who does not know the
language and produces confidently wrong review comments.

**One profile section per language actually in use.** Not per language you might use. A profile
for a language nobody writes is a document that goes stale and then misleads.

---

## Adding a language the checker does not recognize

The checker skips unknown extensions rather than guessing. To teach it a language, add an entry to
`LANGS` in `scripts/check-code.mjs`:

```js
".ext": { name: "Name", block: "brace" | "indent" | "end", line: ["//"], naming: "camel" },
```

`block` is how a callable's body is delimited — braces (C-family), indentation (Python-family), or
an `end` keyword (Ruby/Lua/Elixir-family). If the language does not fit one of those three, leave
it unrecognized: **a checker that guesses produces confident wrong answers, and one wrong finding
costs more trust than ten correct ones earn.**

The laws still apply to that language. Only the automated part is unavailable, and the review
checklist in `references/09-review-checklist.md` covers it by hand.
