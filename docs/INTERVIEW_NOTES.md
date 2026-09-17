# Technical interview notes

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

First measure event ingestion, retention, query selectivity and incident size.
Likely steps are batched ingestion, partitioned event storage, appropriate
indexes, retention policies, a durable worker for rules/correlation, and cursor
pagination. Separate immutable evidence from derived materializations. Introduce
a queue or search engine only when measured throughput and query requirements
justify it. V1 has synchronous ingestion and no distributed scheduler.

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
