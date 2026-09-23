# Technical interview notes

Explain implemented behavior first, then its limits and possible production
extensions. The [seven-minute script](DEMO.md) exercises the main loop;
[validation](VALIDATION.md) records executed outcomes. These notes describe the
current repository, not an assertion that every feature is deployed at a
particular public revision.

## What changed in the expanded workflow?

The original Atlas case, its evidence IDs, and the FastAPI/Next.js/PostgreSQL
architecture remain intact. The repository adds eight inspectable scenarios,
causal replay, typed rule proposals with regression gates, a hypothesis ledger,
an expanded deterministic analyst benchmark, and scoped evidence bundles. These
features expose how decisions are made without introducing another database,
message broker, autonomous agent, or executable detection editor.

The core loop is replay → investigate → assess a hypothesis → compare a rule
change → record a human decision → export and verify. Public mode supports
read-only inspection; local mode supports saved reviews and optional OpenAI.

## Why PostgreSQL? Why no Elasticsearch or graph database?

The application needs transactional relationships among observations, evidence,
alerts, incidents, findings, and reviews. Indexed relational queries and a small
case graph meet the demonstrated workload. Entity edges carry evidence IDs; a
second graph store would add synchronization and operational work without a
measured need. Search and analytics infrastructure should follow retention,
selectivity, and workload measurements rather than a portfolio checklist.

SQLite remains useful for disposable local runs and isolated tests. The public
deployment requires PostgreSQL. A bounded export uses a consistent read snapshot;
shared in-memory SQLite pools are rejected because they cannot guarantee an
independent transaction without affecting another session.

## What does replay actually replay?

It runs inert repository-owned observations through the existing detector and
correlator, producing a bounded causal projection. The browser advances a cursor
over frames for receipt, normalization, detection, alerts, and correlation. It
shows only reached state and withholds completed-scenario evidence and analysis
until the end. No attack is executed and no external telemetry is collected.

Atlas initializes its normal background context before the investigation sequence.
Source-time gaps are divided by playback speed and capped, with that compression
shown in the UI. This is not a wall-clock execution trace or performance test.
Fetching or playing a scenario does not persist a new incident. When correlation
produces none, the result remains an observation scope.

## Why deterministic correlation?

The grouping rationale needs to be reproducible and reviewable. One principal's
alerts form a case only when three distinct rule IDs across two families fit
within 30 minutes of the first alert. Device, session, and IP links provide
context; they are not extra grouping predicates. Some individual temporal rules
separately require a shared session.

This policy can miss unencoded patterns or group benign activity. Its explicit
tradeoff is preferable here to allowing a model to choose its own evidence scope.
The original Atlas case has ten alerts from nine distinct rules across five
families over 22 minutes. Alerts, distinct rules, and rule families are different
quantities. Severity is a rule-mix policy, not a probability of compromise.

## Why separate detection from correlation?

Detection says an observation or sequence satisfies a rule and emits source-cited
signals. Correlation decides whether several signals warrant a shared
investigation. An unfamiliar login may remain weak alone; privilege and access
activity can supply additional context. The components can be tested separately,
and a rule comparison still checks correlation effects across the complete corpus.

## How are rules versioned and reviewed?

Repository rules provide the baseline. Local proposals accept only bounded integer
thresholds/windows for the chosen rule. A proposal is an immutable snapshot tied
to its parent version, complete ruleset digest, and generation. It cannot contain
arbitrary Python or expressions.

An explicit comparison evaluates the full before/after rulesets against independent
scenario obligations. Approval requires a prior run, recomputes the outcome, and
checks that the ruleset, corpus, and result still match what was reviewed. Competing
or obsolete approvals fail rather than silently overwriting one another. Review
reasons and immutable run records preserve the local decision history.

Approval changes future local replay projections. Historical Atlas alerts and case
evidence are preserved. Public mode uses shipped rules and exposes only three
fixed comparisons; it cannot create or approve proposals. Multi-instance rollout,
shadow deployment, and production alert revision retention remain separate work.

## What do PASS, WARN, and BLOCK mean?

BLOCK identifies a proposed-state violation: a missing required rule, a forbidden
rule firing, or an unexpected correlated-incident count. It cannot be approved.
WARN means no measured improvement or increased permitted benign-fixture burden;
the UI requires deliberate acknowledgment and a human reason. PASS means an
observed fixture improvement without a blocking violation.

For APP-002, 1,000 → 1,500 records removes the scheduled-reconciliation match while
retaining required service and Atlas volume signals. A 2,200-record threshold
loses the required service signal and its correlation outcome. A 1,100-record
threshold leaves fixture outcomes unchanged. These are actual computed comparisons
on synthetic observations, not predictions about production traffic.

TP/FN use scenarios that independently require the selected rule; FP/TN use
explicitly benign scenarios. Other scenarios remain in regression checks but are
excluded from that selected-rule matrix. Denominators are displayed. Production
tuning would need outcome labels, representative and held-out traffic, analyst
burden measurement, drift monitoring, and rollout/rollback policies.

## What is a hypothesis, and what does acceptance mean?

The ledger derives a small fixed set of propositions from scoped evidence. It
shows supporting/contradicting citations, evidence-derived status, typed gaps,
and source-time bounds. For example, unfamiliar authentication can partially
support unauthorized control; it cannot prove the actor's identity or intent.
Narrow recorded change approvals and automation allowances can contradict specific
propositions. Missing approval is not proof that a change was unauthorized.

Human review is separate. Acceptance records a working hypothesis without
promoting partial support to confirmation. Version and context checks reject stale
writes. Changes in observations, annotations, derivation, or current findings make
prior reviews stale; current accepted reviews can appear in a report with their
uncertainty intact. Local actor labels are attribution labels, not authenticated
identities. The [ledger contract](HYPOTHESES.md) explains the exact propositions.

## Why AI only after evidence retrieval?

The application resolves case existence and scope before invoking a provider.
The provider cannot decide what it is entitled to retrieve and receives no database
connection, retrieval tools, or mutation functions. The local case service retrieves
a bounded event-time-ordered evidence set; the analyst boundary independently
checks scope, count, and context bytes, then excludes analyst-marked benign rows.
Those limits bound exposure but do not establish completeness for a larger case.

All local demo cases are accessible to the configured analyst label. Authenticated
subject-to-case permissions and tenant isolation are not implemented. Case
membership checks must not be presented as those missing authorization controls.

## How do you prevent hallucinations?

I do not claim to eliminate every incorrect interpretation. The implemented
contract is narrower: proposed factual claims need current-case, in-context
citations and an exact evidence set satisfying deterministic support predicates.
The application validates the structured draft and renders accepted facts through
server templates. One invalid claim rejects the whole proposed answer.

Recognized unsupported questions produce insufficient-evidence behavior; the phrase
guard is not a general entailment classifier. Novel wording still cannot add a
new factual claim type to the output schema. Source observations can be forged,
predicates can have defects, accepted claims can be incomplete, and humans can
misinterpret them. Confidence is a qualitative display label, not a calibrated
probability of compromise.

## How do you handle prompt injection?

Telemetry and user questions are untrusted. The provider receives an allowlisted
projection with instruction/data separation. Raw prose, annotations, user-agent
strings, endpoints, and unnecessary free-form metadata are omitted. The model has
no tools or mutation interface, and structured output is validated independently.

Tested malicious fields are excluded before provider execution. That demonstrates
application enforcement; it does not prove a model resisted instructions it never
received. Historical live attempts, including availability failures, remain
separate from deterministic fixtures. Neither is a universal resistance score.

## How is cross-case leakage checked?

Retrieval selects incident evidence first. The analyst boundary independently
checks allowed scope, incident membership, unique evidence IDs, and context limits.
Output citations must belong to the exact request context, not merely exist in
the database. Unknown, foreign-case, and omitted-context citations reject the draft.
A valid citation also needs support for the selected claim.

Human findings, hypothesis links, rule review runs, and exported references have
their own scoping checks. These are application boundaries; they do not create
an authenticated subject or tenant entitlement. Safe errors omit raw rejected
drafts and credentials. Provider failure returns unavailable rather than a
successful answer or a conclusion of insufficient evidence.

## How do you distinguish volume from exfiltration?

A synthetic account-query event records observed access volume. It does not
establish a transfer destination, copied content, or receipt by an attacker.
The proper claim is high-volume access plus a gap in transfer evidence. Similarly,
a device, IP, or simulated location label does not identify a person or country.
The malware question requires endpoint evidence that this scenario does not have.

## What does the expanded benchmark measure?

Named obligations execute real projection, schema, claim-support, citation,
containment, and rendering code using deterministic and adversarial fixture
providers. Independent expectations are kept outside runtime analyst input. The
hypothesis ledger's narrow counterevidence checks remain distinct from the analyst's
factual support checks; the analyst does not receive the ledger's evaluator labels
as an answer key.

Each metric defines its denominator. Populations overlap and are not independent
samples to add together. Read current counts and failures from the executed result
and [validation record](VALIDATION.md). The original deterministic suite's stored
history, the new baseline benchmark, and historical live OpenAI results are three
separate records. Local rule proposals use the regression workbench and do not
silently alter the baseline analyst benchmark.

## How would you evaluate a model change?

Version the provider/model identifier, prompts, output schema, predicates, and
fixtures together. Start with deterministic boundary checks, then run separately
reported credentialed trials with supported/unsupported questions, adversarial
fields, and human-labeled useful or incomplete answers. Measure sample size,
rejection rates, grounded coverage, latency, and cost with uncertainty. Passing
mock-provider tests is not evidence that a new external model is safe or useful.
The small historical OpenAI record is evidence for its named completed scenarios,
not validation of every future model or release.

## Why not let AI mutate incidents or author the final report?

A plausible recommendation is not an authorized action. The provider cannot save
findings, accept hypotheses, change a case, or approve a report. Separate human
requests perform validated writes and record audit events.

Reports use deterministic templates over current case evidence, entities, approved
findings, and current accepted hypotheses. Case/review changes invalidate approval.
The database retains one current report and lifecycle audit events rather than
signed historical report versions. A human finding's valid citations do not prove
its free-form narrative. Future automation would require its own narrow capabilities,
idempotency, approval policy, and rollback design.

## What does a verified evidence bundle establish?

The exporter reads a bounded committed snapshot in a dedicated consistent read
transaction. It verifies case references and rejects excess rather than truncating
silently. It does not write an export record or invoke a provider. Public exports
omit local human artifacts; local exports include bounded committed review material.
The JSON container holds logical UTF-8 file contents, with no archive extraction.

Browser Web Crypto and the offline CLI compare file membership, byte lengths, and
SHA-256 hashes. VALID means agreement with the supplied manifest. Content changes,
missing files, and unexpected files can be identified. Someone who replaces both
content and the unsigned manifest can produce another valid bundle. Metadata is
also unsigned. This is not proof of authenticity, telemetry truth, authorship,
privileged-database integrity, or legal chain of custody.

## Are events and audit records tamper-proof?

No. ORM hooks and migrated database triggers reject ordinary event/audit updates
and deletes; there are no event edit/delete routes. Immutable rule, regression,
and review records also have database protections. A privileged owner can disable
triggers or alter schema, and the explicit disposable reset recreates demo data.

Stronger production guarantees need least-privilege application roles, independent
retained evidence/audits, delivery-gap monitoring, and tested recovery. Signed or
chained records need independently protected checkpoints and keys. Neither a
trigger nor a replaceable export manifest proves original source truth.

## How would authentication and multi-tenancy work?

A trusted identity provider establishes the subject and tenant. Server policy maps
that subject to capabilities such as read, annotate, review, approve, and export.
Retrieval must apply permissions before model context is built; write routes check
them independently. Model text never grants authority.

Tenant identity must not come from an untrusted request body. Tenant keys would
participate in associations, queries, cache keys, jobs, provider budgets, and export
paths. PostgreSQL row-level security could provide additional enforcement. Tests
would cover API and database read/write isolation. Current local actor labels,
loopback restrictions, and the public read-only mode are demo controls, not this
production IAM design.

## How would streaming and reprocessing work later?

The current finite corpus replay establishes deterministic causal behavior, not a
production streaming system. Production ingestion would need an authenticated
boundary, durable buffering where required, stable idempotency keys, event-time
watermarks, late-arrival handling, and defined ordering semantics.

Persist source observations before deriving alerts. Reprocessing should name its
schema/rule revisions, write separate derived outputs, compare outcomes, and
preserve historical case associations and human review. The implemented local
rule workflow deliberately preserves the canonical case; it is not a distributed
rollout or arbitrary historical-data reprocessing service.

## Why not Kafka? How would this scale?

A finite synchronous demo has no measured need for a broker. Durable buffering,
backpressure, replay retention, and independent consumers could justify one later;
adding it would not solve idempotency or event-time semantics automatically.

Measure ingestion rate and bursts, tenant skew, retention, incident size, query
selectivity, latency targets, and recovery needs first. Likely tools include
batched ingestion, partitions, indexes, bounded-state workers, and separate source
retention. PostgreSQL could remain the transactional case store without retaining
all raw telemetry indefinitely. Load tests and failure exercises should drive
infrastructure choices. No production throughput benchmark is claimed here.

## What remains before a production service?

Authenticated identities and case permissions; tenant isolation; authenticated
ingestion; shared multi-instance budgets and rule rollout; least-privilege database
roles; independent retention; backup/recovery; operational monitoring; provider
privacy review; and broader repeated model evaluation. Cases, context, replay,
review history, and bundles have deliberate bounds. There is no autonomous
remediation, general malware attribution, production streaming, calibrated
confidence, or enterprise-readiness guarantee.
