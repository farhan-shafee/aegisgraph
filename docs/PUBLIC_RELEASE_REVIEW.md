# Public release review

Reviewed on **2026-09-17 UTC**. Scope: publishing the repository for public
inspection, not deploying the application as an internet-facing security service.
The repository remained **private** throughout this audit. Visibility, description,
topics, website, reporting settings and license were not changed.

## Decision

No blocking secret exposure, sensitive image, private path, dependency advisory,
unsupported production claim, or failing local check was identified. The source
is suitable for public portfolio inspection within the limitations below.
No license was selected on the owner's behalf. Public inspection and permissive
open-source reuse are separate decisions.

## Secret scan and repository contents

- Gitleaks **8.30.1**, obtained from its official release with the published SHA-256
  archive checksum verified, found **zero leaks** in both the full reachable Git
  history and a snapshot of tracked/intended release files. Output and reports
  were fully redacted; no secret values were displayed or committed.
- An independent in-memory comparison against configured secret values, combined
  with key/token/private-key, email, path and URL checks, found no exposed local
  secrets. It initially covered 144 tracked files and 181 unique historical blobs.
  The final candidate-file comparison covered 148 files with zero configured-secret
  matches, and all local documentation links resolved.
- A credential-shaped URL in a health-command rejection test is an intentional
  synthetic fixture. The test verifies rejection before any request; it is not a
  usable credential. Database credentials are deliberately public local/ephemeral
  CI demo defaults and must never be reused for a real deployment. Compose binds
  its database port to loopback; CI uses a disposable PostgreSQL service.
- The local `.env` is ignored and untracked. The tracked `.env.example` contains
  placeholders/public demo values. No local databases, private keys, caches,
  runtime helpers, dependency directories, build output, browser traces or
  generated test reports are included in the release files.
- Ignored local artifacts remain on the development machine; they are not part
  of a GitHub clone. Committed evaluation JSON and screenshots are deliberate,
  reviewed evidence rather than temporary test output.

Pattern scanning and exact-value comparison reduce risk; they do not prove that
every possible secret format can be detected. No third-party private repository,
account or production system was tested.

## Git history and attribution

Both existing commits were inspected:

- `3764a742f89139813cf4e429d33bad325087b907` — initial implementation.
- `7293c515d47178405df6fcf93feeeadac067cf64` — interview hardening.

All blobs reachable from local Git refs and commit messages were included in the
history review. No formerly committed `.env`, database, secret or private path
was found. Author and committer email addresses use GitHub noreply addresses;
no private mailbox was identified. Ordinary public author attribution remains.
No history rewrite or credential rotation was indicated by these findings.

The review covers repository refs available locally, not unknown remote forks,
external backups, private GitHub account data or unrelated machine files. The
release commit's staged content is checked separately before push.

## Images, personal data and local configuration

All **24 PNGs** under `docs/screenshots/` were opened and inspected individually:
eight requested portfolio views, four supplementary live/theme/responsive views,
and twelve labeled historical UX baselines. The application SVG icon source was
also inspected. No PNG contained text or EXIF metadata chunks.

No API key, authorization header, private filesystem path, owner username,
personal email, machine detail, unrelated browser content or desktop content was
visible. Identifiers, analyst labels, internal application paths and addresses
belong to the synthetic scenario; IPs use documentation ranges. Keep the existing
images: baselines substantiate the UX audit and supplemental views support the
live-result and theme claims. `02-incident.png` remains the README lead image.

No private machine paths or internal corporate URLs were found in release files
or history. Loopback URLs are documented demo endpoints; `.invalid` URLs are
negative-test fixtures. Other observed hosts serve public source, documentation,
package registry or package-funding links. Configuration uses repository-relative
paths or explicit environment variables rather than a developer home directory.

## Presentation and documentation

The README now opens with the name, one-sentence description, reviewed incident
screenshot, concise technical explanation and architecture/demo links. It covers
detection versus correlation, AI scope and citation support, evaluation, setup,
tests, limitations and production work without a badge wall or performance claims.

- [Documentation guide](README.md) gives a five-minute path to architecture,
  threat model, nine ADRs, rules, correlation, projection, claim/citation validator,
  fixtures, demo and known limitations.
- [Setup](SETUP.md) holds detailed installation, configuration, PostgreSQL, guarded
  reset and credential-free test instructions.
- Stale hardening-CI wording, the moved setup reference and completed UX-plan
  wording were corrected. Historical validation results remain dated.
- [Security policy](../SECURITY.md) states the synthetic/local scope, conditional
  private-reporting route and safe fallback when that route is unavailable.
  No unnecessary contribution or corporate policy template was added.
- Code review found a misleading audit actor label: system events could appear
  as analyst events because the UI guessed from the actor name. The UI now uses
  recorded `actor_type`; two regression tests cover attribution and separately
  labeled AI-assisted findings. Product architecture is unchanged.

Repository-wide searches and targeted source review found no abandoned experiment,
unfinished-work marker, accidental browser debug output or untrusted HTML rendering
requiring release cleanup. Legitimate CLI output and sanitized operational logs
remain. This is not a formal proof that every function is reachable or bug-free.

## Live OpenAI claims

No external model call was made for this release audit. Existing live records
were reviewed against their sanitized evidence and remain historical:

| Supported claim | Evidence and limit |
|---|---|
| Grounded investigation succeeded | Valid structured response; ten supported findings and thirteen citation references checked outside the model |
| Malware false premise was withheld | Insufficient-evidence disposition, zero factual findings, missing endpoint evidence identified |
| Prompt-like telemetry remained untrusted | Tested free-text fields were excluded before the call; supported output and unchanged case state were checked |
| Cross-case and invalid citations were blocked | Five separately local checks; invalid input prevented a call, invalid output rejected the entire answer |
| Limited live validation succeeded | Three named scenarios over six harness requests, retaining three earlier HTTP 429 failures; two additional browser calls succeeded separately |

The 429 cause was not established. These results do not imply universal injection
resistance, model safety guarantees, general accuracy, security certification or
enterprise readiness. Projection of an instruction is distinct from a model
resisting an instruction it actually receives. See the [live record](evaluations/LIVE_VALIDATION.md).

## Fresh validation results

The complete supported local suite was rerun with workstation `.env` loading
disabled, deterministic providers selected, and OpenAI key/model variables removed
from validation child processes. No live key was required.

| Check | Current executed result |
|---|---|
| Ruff lint and formatting | Passed; 31 Python files formatted |
| Backend tests | **146 passed**, two upstream deprecation warnings |
| Frontend formatting and ESLint | Passed |
| TypeScript | Passed |
| Frontend unit/component tests | **25 passed** across eight test files |
| Production Next.js build | Passed |
| Playwright | **13 passed**, retries disabled |
| Deterministic evaluation cases | **28 passed**, zero failed; `live_model_tested=false` |
| Python dependency audit | No known vulnerabilities reported |
| npm dependency audit | Zero known vulnerabilities reported |
| Native PostgreSQL | Current migration at head; read-only API/database smoke passed with 4,026 events and 26 case evidence items |
| Isolated SQLite browser setup | Migrations and clean seed passed before the browser suite |
| Secrets, images and local documentation links | Passed within the review scope described here |

The prior frontend count of 23 is historical; the attribution fix adds two tests.
The other baseline counts were recalculated by execution and remain unchanged.
No Python static type checker is configured, so only TypeScript type checking is
claimed. Dependency audits are point-in-time advisory checks, not proof that
dependencies have no undisclosed vulnerabilities.

Local execution used Windows, Python 3.14.7, Node.js 26.8.2, native PostgreSQL 17.10
and Chrome through Playwright. Browser tests used dedicated manually managed
loopback servers because automatic teardown previously hung in this sandbox;
assertions and the isolated test database were unchanged. CI uses Linux and
automatic server management. Docker startup was not exercised locally. A
non-failing pip-audit cache-write warning did not prevent the advisory check.

## GitHub Actions

The latest completed run at audit preparation,
[hardening CI for `7293c51`](https://github.com/farhan-shafee/aegisgraph/actions/runs/35176511095),
passed all three jobs. Its counts were 146 backend, 23 frontend and 13 browser
tests; those are not substituted for the fresh 25-test frontend result above.

The [workflow](../.github/workflows/ci.yml) retains three practical jobs:

1. Backend: lint/format/tests, fresh PostgreSQL migrations/seed/evaluations/smoke,
   and Python dependency audit.
2. Frontend: format/lint/types/unit tests, production build and npm audit.
3. Browser: isolated SQLite setup, investigation flow and responsive dark/light
   routes, with failure artifacts only when needed.

Workflow-wide `AEGISGRAPH_LOAD_ENV=false` and `AI_PROVIDER=deterministic` make the
credential-free boundary explicit. No job references a private OpenAI secret or
invokes the live runner. Workflow token permissions remain read-only. The exact
release commit's hosted result is checked after push and is available in
[main's Actions history](https://github.com/farhan-shafee/aegisgraph/actions/workflows/ci.yml).
This file does not predeclare an unexecuted hosted run successful.

## License status and recommendation

There is **no project license file**, and GitHub reports no detected license.
No license was added or chosen during this task.

| Choice | Practical implication |
|---|---|
| No license | Default copyright applies; public GitHub users can view/fork under GitHub's terms, but no broad permission to reuse, modify or redistribute is granted. Public source is not automatically open source. |
| MIT | Short permissive terms allow use, modification and distribution, including commercial use, while requiring preservation of copyright/license notices; includes warranty/liability disclaimers. |
| Apache-2.0 | Permissive terms with an explicit contributor patent grant and patent-litigation termination; redistribution also involves license/notices and marking modified files, including NOTICE obligations when applicable. |

**Recommendation: MIT** for a straightforward educational portfolio where easy
reuse is desired. Apache-2.0 is reasonable if an explicit patent grant is a
priority. The owner must make the final choice and confirm rights to license the
work. Leaving the current no-license state does not block public inspection,
but must not be described as an open-source license or a reuse grant.

Sources: [GitHub licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository),
[MIT terms](https://choosealicense.com/licenses/mit/), and
[Apache-2.0 terms](https://www.apache.org/licenses/LICENSE-2.0).

## Recommended GitHub metadata

- **Description:** Evidence-grounded security investigation for a simulated fintech environment.
- **Topics:** `security-engineering`, `incident-response`, `detection-engineering`,
  `ai-security`, `fastapi`, `nextjs`, `postgresql`, `cybersecurity`.
- **Website:** leave blank until there is a public, static portfolio page with the
  reviewed screenshots. No hosted public demo exists; do not use localhost or
  expose this unauthenticated application as the repository website.

The existing description omits the simulation qualifier; changing it is
recommended when the owner publishes. Metadata settings were only read.

## Remaining limitations and owner publication steps

This remains a single-analyst local demo: no production identity/tenant controls,
authenticated ingestion, streaming scale validation, independent immutable audit
retention, recovery operations or general model-robustness measurement. Correctly
typed forged telemetry can still mislead an investigation. No autonomous response,
security certification or production readiness is claimed.

No mandatory source, secret-removal, history-rewrite or screenshot fix remains
before public inspection. The owner retains these publication decisions:

1. Choose MIT/Apache-2.0 or intentionally retain no license, understanding the
   reuse implications above. No license choice has been inferred.
2. Review the exact pushed commit's Actions result before changing visibility.
3. Enable and verify GitHub private vulnerability reporting as part of publication,
   or provide another private contact route. The read-only status request returned
   404 while the repository was private, so availability was not verified and is
   not claimed. GitHub documents this feature for
   [public repositories](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).
4. Apply the suggested description/topics if desired and keep the application
   local. Publishing source and deploying a service have different risk profiles.

The release recommendation is limited to the reviewed public portfolio source,
with passing local checks and no identified disclosure blocker. Repository
visibility remains an explicit owner action.

PUBLIC RELEASE READY
