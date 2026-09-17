# Technical interview notes

Use these answers to explain implemented decisions and their limits. Separate
possible production designs from measured behavior. See [validation](VALIDATION.md)
and [provider evaluations](evaluations/README.md) for executed results.

## Why PostgreSQL? Why no Elasticsearch?

V1 needs transactional relationships among events, evidence, incidents and
findings. Indexed relational queries are enough for thousands of events and a
bounded case timeline. Elasticsearch would add ingestion synchronization,
operational overhead and another authorization surface. I would benchmark
retention and query requirements before adding specialized search or analytics.

## Why deterministic correlation?

The grouping rationale must be reproducible, inspectable and testable. V1 groups
by principal and event time: at least three distinct rule IDs across at least two
families within 30 minutes of the first alert. Device/session/IP links provide
investigation context, not additional grouping conditions. Some temporal
detections separately require matching sessions. This will miss unencoded patterns and can merge benign activity;
that tradeoff is documented. Model-based grouping would make the evidence scope
itself probabilistic and harder to evaluate.

## Why AI only after evidence retrieval?

The application checks incident existence and resolves case scope before invoking the provider. The provider
cannot decide what it is entitled to retrieve. This reduces context size and
prevents the whole database from being sent to an external API. Authorization
belongs in the application, not in natural-language instructions.

The local service retrieves the earliest 50 evidence rows, then the analyst
boundary excludes rows marked benign and discloses that count. The boundary also
enforces an independent 80-row and 64,000-byte context limit. This bounds exposure
and cost; it is not a completeness guarantee for a larger case. All local demo
cases are accessible to the fixed analyst. Production subject-to-case permissions
are still future work.

## How do you prevent hallucinations?

I don't claim to eliminate every incorrect interpretation. The implementation
enforces a narrower contract: factual findings need current-case, in-context
citations and supported typed claim predicates. The server renders the accepted
facts and cited summary instead of trusting arbitrary model prose. A single invalid
claim rejects the whole answer. Recognized false-premise questions produce an
insufficient-evidence result; the phrase guard is not a universal entailment
classifier. Novel question wording still cannot introduce new factual claim types.
Source telemetry can still be false, and supported
facts can still be selected incompletely or interpreted poorly by a human.

The confidence field is a fixed qualitative display label associated with the
accepted result. It is not calibrated against an empirical probability of
compromise. The possible-account-misuse statement is explicitly a hypothesis.

## How do you handle prompt injection?

All telemetry and the analyst's question are untrusted data. The provider gets an
allowlisted projection with explicit instruction/data separation. Raw strings,
annotations, user agents, endpoint strings, and free-form metadata are omitted.
The model has no
tools or mutation interface. Structured output is independently checked. Tests
include malicious metadata and attempted policy overrides. These checks are not
a measured universal live-model resistance rate.

## How would this scale?

One billion events per day averages roughly 11,574 events per second before burst
headroom, replication, indexes, replay, or late arrivals. At an illustrative one
kilobyte per event, that is roughly one terabyte of raw data per day. These are
sizing calculations, not measured AegisGraph throughput.

First measure event ingestion, retention, query selectivity and incident size.
Likely steps are batched ingestion, partitioned event storage, appropriate
indexes, retention policies, a durable worker for rules/correlation, and cursor
pagination. Separate immutable evidence from derived materializations. Introduce
a queue or search engine only when measured throughput and query requirements
justify it. V1 has synchronous ingestion and no distributed scheduler.

At that scale I would separate durable ingestion, independently retained source
observations, partitioned canonical storage, bounded-state rule workers, derived
query indexes, and a transactional case-management store. PostgreSQL could remain
the case store without holding every raw event indefinitely. Establish peak rates,
tenant skew, latency targets, retention, and recovery requirements before choosing
infrastructure. Load tests and failure exercises would determine the actual design.

## What changes for production?

Real authentication, case authorization, tenant isolation, CSRF/session handling,
TLS, ingestion authentication and quotas, rate limits, managed secrets, least-
privilege DB roles, operational monitoring, recovery procedures, external audit
retention, provider privacy review and independent security assessment. Current
loopback binding and a fixed local analyst are a demo boundary, not production IAM.

## How would multi-tenancy work?

Tenant identity must be derived from trusted authentication, never a request body.
Tenant keys must participate in every event/evidence/incident association and
query. Consider PostgreSQL row-level security as additional enforcement, plus
tenant-scoped object storage, cache keys, jobs, model budgets and export paths.
Test both read and write isolation at the API and database layers. V1 does not
implement these controls and should not be presented as multi-tenant.

## How would authorization work?

A real identity provider establishes the subject. A server policy maps the
subject to case permissions and capabilities such as read, annotate, assign,
approve and export. Retrieval applies these permissions before building model
context. Write routes check them independently. Audit records should distinguish
the authenticated human requester, system process and provider. A model response
never grants a permission. V1 instead records a configured human label or system
label, and provider metadata on analysis records. Its tests cover case membership,
foreign-case mutation rejection, and read-only provider boundaries; they do not
establish authenticated user or tenant isolation.

## Why not let AI mutate incidents?

A plausible recommendation is not an authorized action. Keeping the provider
read-only removes a large class of prompt-injection consequences and makes
auditability clearer. Analyst changes use separate validated requests with
explicit save/approve actions. Any future automation needs narrowly scoped
capabilities, idempotency, approval and rollback design of its own.

## Why not a graph database?

The incident graph is a small evidence-backed relational projection. SQL joins
are enough to connect a user to sessions, devices, IPs and accessed resources.
A graph database might help deep cross-case traversals later, but V1 has no
measured workload that warrants the extra storage and synchronization system.

## How would streaming ingestion work later?

Keep adapters and canonical validation independent from transport. Introduce an
authenticated ingestion boundary and durable queue; define idempotency keys,
event-time watermarks, late arrival handling, ordering assumptions and replay
semantics before adding streaming rule evaluation. Persist observations before
deriving alerts. Test equivalent results between replay and live processing.

## How would you evaluate model changes?

Version the provider/model identifier, prompts, output schema, claim predicates
and dataset together. Run deterministic boundary tests first, then a separately
reported live-provider suite with repeated trials, false-premise prompts,
adversarial source fields and human-labeled useful/incomplete answers. Measure
rejections, valid grounded claims, useful coverage, latency and cost. Report
sample sizes and uncertainty. Passing mock tests is not evidence that a new
external model is safe or useful.

## How do you distinguish high data volume from exfiltration?

The synthetic application event records access volume. It does not establish
destination, actual records exported, or a data transfer to an attacker. The
report should state observed access and the missing transfer/content evidence.
Likewise, an IP or simulated location label does not establish a person's country.

## Why is the report generated from a template?

The report needs stable evidence references and a visible review lifecycle. V1
uses a deterministic template over current-case evidence, entities, workflow
state, and analyst-approved findings. The model does not author or approve it.
Case changes invalidate the report, clear approval metadata, and block renewed
approval until regeneration and review. The database holds one current report
plus lifecycle audit events, not historical signed report snapshots. Human
findings remain subject to human judgment; valid citations alone do not prove
their free-form narrative.

## Are events and audits tamper-proof?

No. Source-event edits and deletes are blocked by ORM hooks, and there are no event
or audit edit routes. Migrations also install PostgreSQL/SQLite triggers that
reject ordinary event and audit UPDATE/DELETE statements. Those controls do not
stop a privileged owner from disabling triggers or changing schema. The explicit
CLI reset intentionally drops and recreates the demo tables. Production requires
restricted roles, independent retained copies, and verified backups. This is
enforced append-only behavior for ordinary operations, not cryptographic integrity
or proof that the original telemetry is true.

## Why not Kafka?

V1 processes a finite synthetic dataset synchronously. There is no measured delivery
or throughput requirement that needs a broker. Durable buffering, backpressure,
replay, and independent consumers would be reasons to consider Kafka or another
log service later. Adding a broker alone does not define correct idempotency,
ordering, late-event handling, or alert generation. Those semantics come first.

## Why are detections and correlation separate?

Detection says that an observation or sequence satisfies a rule and emits an alert
with evidence. Correlation decides whether several alerts deserve one investigation.
An unfamiliar login can remain a weak signal while related privilege and access
activity creates a case. Rule changes and grouping changes can be tested separately.
The default case has ten alerts from nine distinct rules across five families over
22 minutes. The catalog has ten rules; repeated authentication failure does not fire
in that case. Alert count and distinct-rule count are different quantities.

## How is cross-case leakage prevented today?

Retrieval selects evidence for the current incident before invoking the provider.
The analyst boundary independently verifies incident membership, allowed incident
IDs, unique evidence IDs, and context limits. The provider gets no retrieval tool
or database connection. Output citations must be members of the exact request
context, not merely records that exist somewhere in the database. This enforces
case membership; it does not supply missing authenticated subject-to-case access.

## What happens if the model cites nonexistent evidence?

The entire proposed answer is rejected and no findings render. The same applies to
a real ID from another case, or a current-case ID omitted from bounded context.
A valid citation also needs an exact evidence set supporting the proposed claim.
Safe error codes identify the failure without logging raw drafts or credentials.
An upstream HTTP failure yields provider-unavailable, not a grounded answer and
not an insufficient-evidence conclusion.

## What does the malicious-telemetry evaluation prove?

The fixture puts instruction-like content in untrusted raw/metadata/annotation
fields. Projection removes these fields before provider execution. Verifying that
removal and unchanged case state tests application enforcement. It does not prove
a live model resisted text it never received. A live request that returns an HTTP
error is not a passed injection test. Consult the separate recorded live results;
never present deterministic fixtures as external-model performance.

## How would the audit trail become append-only in production?

Migrated V1 tables already reject ordinary audit UPDATE/DELETE statements. The
database owner can remove those triggers, and disposable-demo reset intentionally
recreates the tables. Stronger production guarantees need separate application
and audit-admin roles, independent append-only/WORM retention, delivery-gap
monitoring, and tested backup/restore. Signed or chained records need independently
protected checkpoints and keys to detect the intended class of changes. A database
trigger alone is not cryptographic tamper-proof storage.

## How would events be reprocessed?

Keep immutable source observations with explicit adapter/schema versions. Run a
named replay against chosen normalization and rule revisions, using stable
idempotency keys and separate derived outputs. Compare results before replacing
active materializations. Preserve historical case associations and human review;
reprocessing must not silently rewrite evidence cited by an approved report. V1
offers deterministic reseeding of disposable data, not a production replay system.

## How would detection rules be versioned?

The JSON rules are versioned in Git and checked with fixtures today. Production
alerts should also retain the exact rule revision/hash, effective configuration,
schema version, and evidence references. Review changes with positive/negative
fixtures, temporal boundary cases, shadow runs, and rollout/rollback policies.
Git history alone does not make an alert retain its historical rule semantics.

## How would false positives be tuned?

Collect analyst labels with reasons and confirmed outcomes. Measure alert volume,
review burden, cohort behavior, and precision/recall only where labels support it.
Tune thresholds and windows using held-out data, then test correlation effects so
suppressing one signal does not hide a meaningful sequence. Time-bound exceptions
and monitor drift. One synthetic incident cannot establish detection quality.

## What are the current V1 limitations?

Fixed local identity, no tenant isolation, synchronous finite ingestion, synthetic
thresholds, bounded case and model context, a narrow claim vocabulary, no autonomous
response, no production replay or streaming, no retained report versions, and
privileged-owner bypass of event/audit triggers. Source observations can be false,
supported claims can be incomplete, and provider availability is independent of
deterministic test success. These boundaries are explicit in the UI and documents.
