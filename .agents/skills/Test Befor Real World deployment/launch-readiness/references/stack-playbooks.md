# Stack Playbooks — the real command for your stack

The gate files say *what* to prove. This file says *what to type*. Find your stack, use the
commands, and remember G0.03: **every command must be observed to run before you trust it.**

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**Order of trust when finding a project's real commands:**
1. The CI workflow file (`.github/workflows/*.yml`, `.gitlab-ci.yml`) — these commands demonstrably work.
2. `package.json` scripts, `Makefile`, `Justfile`, `Taskfile.yml`, `pyproject.toml` `[tool.*]`.
3. The README.
4. The defaults below.

---

## Node.js / TypeScript

| Need | Command |
|---|---|
| Install (frozen) | `npm ci` · `pnpm i --frozen-lockfile` · `yarn --immutable` · `bun install --frozen-lockfile` |
| Build | `npm run build` |
| Test | `npm test` · `npx vitest run` · `npx jest --ci` |
| Random order | `npx jest --randomize` · `npx vitest --sequence.shuffle` |
| Coverage | `npm test -- --coverage` |
| Typecheck | `npx tsc --noEmit` |
| Lint | `npx eslint . --max-warnings=0` |
| Format check | `npx prettier --check .` |
| Dead code | `npx knip` · `npx depcheck` · `npx ts-prune` |
| Vulns | `npm audit --audit-level=high` · `pnpm audit` · `osv-scanner -r .` |
| Licences | `npx license-checker --production --summary` |
| Bundle size | `npx source-map-explorer 'dist/**/*.js'` · `npx vite-bundle-visualizer` |
| SBOM | `npx @cyclonedx/cyclonedx-npm --output-file sbom.json` |
| E2E | `npx playwright test` · `npx cypress run` |
| A11y | `npx @axe-core/cli "$URL" --exit` · `npx pa11y-ci` |
| Load | `npx autocannon -c 50 -d 30 "$URL"` |
| Lighthouse | `npx lighthouse "$URL" --output=html --output-path=./lh.html --quiet` |

```bash
LRK run G1.03 -- npx tsc --noEmit
LRK run G1.04 -- npx eslint . --max-warnings=0
LRK run G1.12 -- npm audit --audit-level=high
LRK run G2.02 -- bash -c 'rm -rf node_modules && npm ci && npm test'
LRK run G2.15 -- npx playwright test
```

**Node-specific traps.** `npm test` exits 0 with "no test specified" when no script exists — read
the output, not just the exit code. `npm install` is not `npm ci`; only the latter respects the
lockfile. `--max-warnings=0` is required or ESLint exits 0 with a screen full of warnings.

---

## Next.js / React / Vite / Remix

| Need | Command |
|---|---|
| Production build | `npx next build` · `npx vite build` |
| Start production build | `npx next start` |
| Bundle analysis | `ANALYZE=true npx next build` (with `@next/bundle-analyzer`) |
| Route inventory | `find app pages -name "page.tsx" -o -name "route.ts" \| sort` |

**Traps.** `next dev` and `next build` behave differently — always audit the production build.
Server components hide errors that only appear in the server log, so read it. Environment variables
prefixed `NEXT_PUBLIC_` are **shipped to the browser**; grep for them and confirm none is a secret:
`git grep -n "NEXT_PUBLIC_" | grep -iE "key|secret|token|password"`.

---

## Python

| Need | Command |
|---|---|
| Install | `pip install -r requirements.txt` · `poetry install --sync` · `uv sync --frozen` |
| Test | `pytest -q` |
| Random order | `pytest -p randomly` (needs `pytest-randomly`) |
| Coverage | `pytest --cov --cov-report=term-missing` |
| Typecheck | `mypy .` · `pyright` |
| Lint | `ruff check .` · `flake8` · `pylint <pkg>` |
| Format check | `black --check .` · `ruff format --check .` |
| Vulns | `pip-audit` · `safety check` · `osv-scanner -r .` |
| SAST | `bandit -r . -ll` · `semgrep --config=auto --error` |
| Licences | `pip-licenses --format=markdown` |
| Load | `locust -f load.py --headless -u 50 -r 5 -t 5m` |

```bash
LRK run G1.03 -- mypy .
LRK run G1.12 -- pip-audit
LRK run G4.25 --title "bandit SAST" -- bandit -r . -ll
LRK run G2.02 -- bash -c 'python -m venv /tmp/v && /tmp/v/bin/pip install -r requirements.txt && /tmp/v/bin/pytest -q'
```

**Traps.** `requirements.txt` without pinned versions is not a lockfile — use `pip-compile`,
`poetry.lock`, or `uv.lock`. A stale `__pycache__` hides import errors; clear it for G2.02.

---

## Django

| Need | Command |
|---|---|
| Deploy checks | `python manage.py check --deploy --fail-level WARNING` |
| Test | `python manage.py test` · `pytest` |
| Migrate | `python manage.py migrate` |
| Migration plan | `python manage.py migrate --plan` |
| Rollback | `python manage.py migrate <app> <previous_migration>` |
| Missing migrations | `python manage.py makemigrations --check --dry-run` |
| SQL for a migration | `python manage.py sqlmigrate <app> <number>` |

```bash
LRK run G4.16 --title "django deploy checks" -- python manage.py check --deploy --fail-level WARNING
LRK run G5.02 --title "rollback executed" -- bash -c 'time python manage.py migrate orders 0012'
```

`check --deploy` alone covers a surprising share of G4: `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`,
HSTS, secure cookies, and SSL redirect. Run it first.

---

## Go

| Need | Command |
|---|---|
| Build | `go build ./...` |
| Test | `go test ./...` |
| Race detector | `go test -race ./...` — **run this; it finds real concurrency bugs (G3.11)** |
| Shuffle | `go test -shuffle=on ./...` |
| Coverage | `go test -coverprofile=c.out ./... && go tool cover -func=c.out` |
| Vet | `go vet ./...` |
| Lint | `golangci-lint run` |
| Vulns | `govulncheck ./...` |
| Licences | `go-licenses report ./...` |
| Unused deps | `go mod tidy && git diff --exit-code go.mod go.sum` |

```bash
LRK run G3.11 --title "race detector" -- go test -race ./...
LRK run G1.12 -- govulncheck ./...
```

---

## Rust

| Need | Command |
|---|---|
| Build | `cargo build --release` |
| Test | `cargo test --all-features` |
| Lint | `cargo clippy --all-targets -- -D warnings` |
| Format | `cargo fmt --check` |
| Vulns | `cargo audit` · `cargo deny check` |
| Coverage | `cargo llvm-cov --summary-only` |
| Unused deps | `cargo +nightly udeps` |

---

## Java / Kotlin

| Need | Maven | Gradle |
|---|---|---|
| Build | `mvn -B package` | `./gradlew build` |
| Test | `mvn -B test` | `./gradlew test` |
| Coverage | `mvn jacoco:report` | `./gradlew jacocoTestReport` |
| Vulns | `mvn org.owasp:dependency-check-maven:check` | `./gradlew dependencyCheckAnalyze` |
| Licences | `mvn license:aggregate-third-party-report` | `./gradlew generateLicenseReport` |

Spring Boot: confirm `/actuator` endpoints are secured or disabled in production (G4.23) —
`/actuator/env` and `/actuator/heapdump` are full credential disclosures.

---

## .NET

| Need | Command |
|---|---|
| Build | `dotnet build -c Release /warnaserror` |
| Test | `dotnet test --logger "console;verbosity=detailed"` |
| Coverage | `dotnet test --collect:"XPlat Code Coverage"` |
| Vulns | `dotnet list package --vulnerable --include-transitive` |
| Outdated | `dotnet list package --outdated` |
| Format | `dotnet format --verify-no-changes` |

---

## Ruby / Rails

| Need | Command |
|---|---|
| Install | `bundle install --deployment` |
| Test | `bundle exec rspec` · `bin/rails test` |
| Lint | `bundle exec rubocop` |
| Vulns | `bundle audit check --update` |
| SAST | `bundle exec brakeman -q -w2` — **Rails-specific and very effective for G4** |
| Migrate | `bin/rails db:migrate` |
| Rollback | `bin/rails db:rollback STEP=1` |
| Migration status | `bin/rails db:migrate:status` |

---

## PHP / Laravel

| Need | Command |
|---|---|
| Install | `composer install --no-dev --optimize-autoloader` |
| Test | `vendor/bin/phpunit` · `php artisan test` |
| Static analysis | `vendor/bin/phpstan analyse --level=8` · `vendor/bin/psalm` |
| Vulns | `composer audit` |
| Migrate / rollback | `php artisan migrate` / `php artisan migrate:rollback` |

Confirm `APP_DEBUG=false` and `APP_ENV=production` in the target (G4.20) — Laravel's debug page
prints environment variables, including every secret, to any visitor.

---

## Flutter / Dart

| Need | Command |
|---|---|
| Analyze | `flutter analyze --fatal-infos` |
| Test | `flutter test --coverage` |
| Integration | `flutter test integration_test` |
| Build Android | `flutter build appbundle --release` |
| Build iOS | `flutter build ipa --release` |
| Size | `flutter build apk --analyze-size --target-platform android-arm64` |

---

## React Native

| Need | Command |
|---|---|
| Test | `npx jest` |
| Android release | `cd android && ./gradlew bundleRelease` |
| iOS release | `xcodebuild -workspace ios/App.xcworkspace -scheme App -configuration Release` |
| E2E | `npx detox test -c ios.sim.release` · `maestro test flows/` |

Mobile-specific G8.16 checks matter most here: permission denial, backgrounding, and deep links
from a cold start.

---

## Docker / Kubernetes

| Need | Command |
|---|---|
| Build | `docker build -t app:rc .` |
| Image vulns | `docker scout cves app:rc` · `trivy image app:rc` · `grype app:rc` |
| Dockerfile lint | `hadolint Dockerfile` |
| Image size | `docker images app:rc --format "{{.Size}}"` |
| Runs as non-root? | `docker run --rm app:rc id` — **must not print `uid=0`** |
| Secrets in layers | `docker history --no-trunc app:rc \| grep -iE "key\|secret\|token\|password"` |
| K8s manifest lint | `kubeconform -strict manifests/` · `kubectl apply --dry-run=server` |
| K8s security | `kubesec scan deployment.yaml` |
| Graceful shutdown | Confirm `terminationGracePeriodSeconds` exceeds your drain time (G7.11) |

```bash
LRK run G1.12 --title "container CVEs" -- trivy image --severity HIGH,CRITICAL app:rc
LRK run G4.23 --title "container runs as non-root" -- docker run --rm app:rc id
```

**Container traps.** Secrets passed as build args are baked into the image layers permanently.
`FROM node:latest` is not reproducible — pin a digest. A container running as root turns any
application vulnerability into a host compromise.

---

## Static sites / JAMstack

Most of G5, G6, G7, and G10 will be legitimately N/A — record the reason for each.
Still fully applicable: G1 (secrets, dependencies, bundle size), G4.16 (security headers),
G4.17 (TLS), G8 (all of it), G9 (privacy, cookies, licences), G11 (rollback = redeploy the previous
build; still time it).

---

## No stack detected / a language not listed

Fall back to first principles:

1. Find how it is built: `ls`, `cat Makefile`, read the CI workflow, read the Dockerfile.
2. Find how it is tested: search for `test`, `spec`, `_test`, `Test` in filenames.
3. If there is genuinely no build and no test system, that **is** the G0/G2 finding. Record it and continue — you can still do G3 (run it and try to break it), G4 (probe the running system), G8 (use it), G9 (read the policies), and G11 (rehearse the rollback).

A readiness review of software with no test suite is still worth doing. It just produces a shorter
report and a much longer blocker list — which is exactly the information the owner needs.

---

## Cross-stack utilities worth installing once

| Tool | What it gives you | Gate |
|---|---|---|
| `gitleaks` | Secret scanning over full git history | G1.10 |
| `semgrep` | Multi-language SAST | G4.25 |
| `trivy` | Container, filesystem, and dependency CVEs | G1.12, G4.25 |
| `osv-scanner` | Vulnerabilities across every ecosystem, one tool | G1.12 |
| `syft` | SBOM for anything | G4.22 |
| `k6` | Load, stress, and soak testing | G6.06–G6.08 |
| `zap-baseline` | DAST against a running app | G4.25 |
| `axe-core/cli` | Accessibility | G8.03 |
| `lighthouse` | Frontend performance | G6.03 |
| `toxiproxy` | Latency and failure injection | G7.02, G7.03 |
