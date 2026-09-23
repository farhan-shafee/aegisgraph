# AegisGraph personal-site handoff

This file supplies portfolio copy and assets for a separate website update. No
personal website repository has been changed. The copy describes the current
AegisGraph repository. Confirm the hosted revision in [deployment](DEPLOYMENT.md)
before publishing links or language that imply the expanded workflow is live.

## Project card

**Title:** AegisGraph

**Subtitle:** Evidence-grounded security investigation for a simulated fintech environment.

**Short description:** Replay synthetic telemetry, investigate cited evidence,
assess working hypotheses, compare detection-rule changes, and verify exported
investigations. AegisGraph combines FastAPI, Next.js, and PostgreSQL with a bounded
analyst interface and explicit human review. Public mode provides deterministic,
read-only exploration; saved reviews and optional OpenAI analysis belong to the
local workflow.

**Suggested tags:** Security engineering, detection engineering, incident response,
AI security, Python, FastAPI, TypeScript, Next.js, PostgreSQL.

**Primary links:** [Demo](https://aegisgraph.farhan-shafee.com),
[source](https://github.com/farhan-shafee/aegisgraph),
[architecture](https://github.com/farhan-shafee/aegisgraph/blob/main/docs/architecture/SYSTEM.md),
[seven-minute walkthrough](https://github.com/farhan-shafee/aegisgraph/blob/main/docs/DEMO.md).

The replay and comparison entry points are `/replay?scenario=atlas-compromise`
and `/detections/APP-002`. Evaluations live at `/evaluations`. Evidence, hypotheses,
and export are tabs in the canonical Atlas case. Promote these deeper demo links
only after the deployed revision exposes those capabilities.

## Case-study copy

### Making investigation decisions inspectable

AegisGraph explores how security tooling can make the path from observation to
decision easier to inspect. A fictional fintech account generates identity, API,
endpoint, and application telemetry. Deterministic detections produce source-cited
alerts, and a principal/time/rule-family policy forms investigations. The original
Atlas case remains preserved while an eight-scenario corpus adds benign,
ambiguous, and conflicting context.

I built a causal replay that exposes only the state reached at its current cursor.
The investigation workspace connects a timeline, source records, and relational
entity links. A hypothesis ledger separates evidence-derived support from human
acceptance and identifies the observations needed to resolve uncertainty. A local
detection workbench saves bounded parameter proposals, runs full-corpus
comparisons, and records explicit review decisions. Its gates expose both useful
fixture tradeoffs and changes that lose required signals.

The analyst provider receives a bounded projection and proposes typed claims with
evidence IDs. Application code validates schema, exact context membership, and
support predicates before rendering statements. Deterministic fixtures and a
separate historical OpenAI validation record make those boundaries inspectable.
The public workflow remains deterministic and read-only.

An evidence export captures a consistent committed snapshot with a SHA-256
manifest. Browser and offline verification identify changes against that supplied
manifest. The manifest remains unsigned and replaceable, so this establishes hash
agreement rather than authenticity or source truth. Authenticated identities,
tenant isolation, independent retention, and production ingestion remain future
work. The implementation keeps one Next.js frontend, one FastAPI service, and
PostgreSQL, hosted through Vercel and Railway.

## Five résumé bullets

- Built an evidence-grounded security investigation application using FastAPI,
  Next.js, and PostgreSQL, with deterministic detection and correlation over
  synthetic fintech telemetry.
- Implemented causal replay across eight scenarios while preserving canonical
  case evidence and distinguishing observation scopes from correlated incidents.
- Designed bounded rule parameters, immutable proposal and regression records,
  stale-baseline checks, and human PASS/WARN/BLOCK review workflows.
- Implemented structured analyst output validation, exact-context citation checks,
  deterministic claim-support predicates, and a separately reviewed hypothesis
  ledger with explicit evidence gaps.
- Built scoped consistent-snapshot exports with browser and offline SHA-256
  verification, supported by deterministic boundary evaluations and local/public
  browser workflow tests.

## Five LinkedIn bullets

- I expanded AegisGraph around a visible investigation loop: replay observations,
  inspect evidence, assess a hypothesis, compare a rule change, and verify an export.
- The corpus includes suspicious, benign, ambiguous, and mixed-context scenarios
  so the demo can show uncertainty and missed obligations alongside useful signals.
- Rule comparisons show the underlying scenario changes and explicit measurement
  populations. The displayed results describe synthetic fixtures rather than
  production detection accuracy.
- The AI boundary validates typed claims and their exact evidence references in
  application code. Public exploration is deterministic; prior live OpenAI
  validation is documented separately with its limits and availability failures.
- Export verification checks exact file contents against an unsigned manifest.
  I document what this detects, what it cannot authenticate, and which production
  controls remain unimplemented.

## Screenshot selection and captions

These captures show actual synthetic application views reviewed during the
September 23 public-mode production rehearsal. They do not, by themselves,
establish which remote revision was deployed. Keep captions close to the images.

| Asset                                                           | Suggested use       | Caption / alt text                                                                                                                 |
| --------------------------------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| [Replay](screenshots/v2-replay.png)                             | Lead project image  | Atlas observations progress through normalization, detection, and correlation; source-time gaps are compressed and disclosed.      |
| [Hypotheses](screenshots/v2-hypotheses.png)                     | Explain uncertainty | Evidence-derived hypothesis status, supporting citations, and typed investigation gaps remain separate from human acceptance.      |
| [Detection regression](screenshots/v2-detection-regression.png) | Engineering detail  | A computed APP-002 comparison exposes parameter changes, scenario outcomes, a review gate, and synthetic measurement denominators. |
| [Bundle verification](screenshots/v2-bundle-verification.png)   | Integrity boundary  | Exact UTF-8 content hashes match the supplied unsigned manifest; VALID does not authenticate the source.                           |
| [Evaluations](screenshots/v2-evaluations.png)                   | Validation detail   | Named deterministic obligations show expected and observed behavior with defined metric populations.                               |

Use Replay as the hero and Detection regression as the first engineering detail.
On a short project page, two or three images are enough; the full screenshot guide
can carry the rest. Preserve readable application text when cropping, and avoid
invented device mockups or changing displayed outcomes.

## Publication facts and limits

Use [current validation](VALIDATION.md) for exact executed test counts and CI
results. The expanded deterministic analyst benchmark, original stored boundary
suite, and [historical live OpenAI record](evaluations/LIVE_VALIDATION.md) are
separate evidence sources. Do not combine their totals into an accuracy claim.

The prior OpenAI record supports a completed grounded investigation, structured
response validation, external evidence checks, insufficient evidence for the
tested malware premise, and exclusion of tested malicious telemetry. It does not
establish universal prompt-injection resistance or general model safety. The
current public workflow uses deterministic analysis and no OpenAI spend.

The project is MIT-licensed, uses bundled synthetic telemetry, and has no production
authentication, tenant isolation, autonomous remediation, enterprise-readiness
claim, or security certification. Repository description suggestion:
**Evidence-grounded AI security investigation for a simulated fintech environment.**
