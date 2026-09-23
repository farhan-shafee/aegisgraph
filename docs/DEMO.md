# AegisGraph: seven-minute interview walkthrough

The story is one loop: replay observations, investigate the evidence, assess a
hypothesis, compare a detection change, and export a verifiable snapshot. All
bundled observations are synthetic. Keep [interview notes](INTERVIEW_NOTES.md)
open for follow-up questions.

## Prepare and rehearse

Use the [setup guide](SETUP.md). For a fresh disposable local demo, stop its API,
then run these commands from the repository root with the virtual environment
active:

```sh
python -m aegisgraph.cli demo-reset
python -m aegisgraph.cli demo-api
```

Start `npm run dev --prefix apps/web` in another terminal and open
[localhost:3000](http://127.0.0.1:3000). Run
`python -m aegisgraph.cli demo-health` from an activated API terminal. The default
provider is explicitly deterministic; no external API key is needed.

`demo-reset` deletes edits and saved runs only in the reserved disposable demo
database. Its matching PostgreSQL option is documented in [setup](SETUP.md).
Do not reset a database containing work you intend to keep. Optional live OpenAI
execution is a separate, explicitly configured exercise; it is not required for
this script.

Before presenting:

- Confirm the canonical Atlas fixture has 4,026 events, ten alerts, and 26 evidence
  items, and that local APP-002 is at its shipped 1,000-record threshold.
- Rehearse Replay at 20× once. Idle gaps are visibly compressed, so this is an
  explanatory playback rather than a wall-clock attack simulation.
- Open Replay, the Atlas case, APP-002, and Evaluations in convenient tabs. A
  second case tab on Export avoids navigating back at the end.
- For the hosted alternative, check the [verified deployment record](DEPLOYMENT.md)
  and visible capabilities first. Use the public comparison path below; public
  visitors cannot save rule or case reviews.

## 00:00–00:30 — Frame the problem

Open Overview and point out the original Atlas investigation.

> AegisGraph is an evidence-grounded security investigation application for a
> simulated fintech environment. I wanted the reasoning to be inspectable: which
> observations produced a signal, why signals became a case, which claims the
> evidence supports, and what remains unknown.

> The hosted path is a Vercel Next.js frontend, Railway FastAPI, and PostgreSQL.
> Public mode is read-only and deterministic. Local mode adds explicit human
> review and optional OpenAI analysis.

## 00:30–01:35 — Replay Atlas at 20×

Open **Replay**, select **Atlas account investigation**, set **Playback speed**
to **20×**, and click **Start**. Briefly use **Pause**, **Step**, and **Resume**.

> The 4,000 normal background records are initialized before playback. The 26
> investigation observations then pass through telemetry, normalization,
> detections, alerts, and correlation. The cursor only exposes reached state;
> the completed investigation is withheld until playback finishes.

Point out the first incident at 14:03 UTC and later changes as privileged access
and application activity arrive. Source-time gaps are capped and disclosed; do
not describe the playback speed as a throughput measurement.

> Correlation requires one principal, at least three distinct rules across two
> families, and a 30-minute window. A weak anomaly can remain an alert instead of
> automatically becoming an incident.

At completion, use **Open canonical Atlas case**. The replay is an ephemeral
projection; this link opens the separate persisted investigation.

## 01:35–02:20 — Follow evidence and relationships

Open one timeline observation and inspect its evidence ID, timestamp, actor,
source/device/session, and canonical event. Close the drawer, open **Entities**,
select the unfamiliar device, and follow its evidence relationship.

> The graph is derived from relational evidence associations. A relationship
> helps inspect the sequence; it does not establish the person behind an account.
> An annotation is separate from the source event. Ordinary event edits are
> blocked, but a privileged database owner remains outside that guarantee.

Return to **Timeline** and leave the analyst visible. The canonical fixture and
its evidence IDs are preserved across replay and rule tuning.

## 02:20–03:15 — Ask two different questions

Ask exactly **What most likely happened?** Inspect one finding and open its
citation. Name the visible provider: the ordinary demo is **deterministic**.

> The provider selects typed claims and supporting evidence IDs. The application
> validates their schema, current-case membership, inclusion in the actual
> bounded context, and claim support outside the model. Accepted prose comes
> from server templates; a real citation is not a license for arbitrary claims.

Then ask **What malware family was used?** Show the insufficient-evidence result.

> Identity and access observations do not establish malware execution or a
> malware family. This is a deliberate evidence limit. High access volume also
> does not establish exfiltration.

Provider unavailability is a different outcome. Do not present a failed external
request as a successful insufficient-evidence test.

## 03:15–04:00 — Inspect a working hypothesis

Open **Hypotheses**. Inspect **Account activity reflects unauthorized control**,
its supporting citation, and **What would confirm or reject this?** Show the
missing account-control and session evidence.

> Evidence-derived status is separate from human acceptance. Unfamiliar activity
> can partially support unauthorized control; it cannot confirm identity or
> intent. Accepting a working hypothesis records a review without upgrading the
> evidence status. Changed context makes old reviews stale.

Supporting and contradicting evidence have separate places in the ledger; do not
imply Atlas contains a contradiction where that list is empty. Approved
administration and scheduled reconciliation provide useful follow-up examples of
narrow counterevidence.

## 04:00–05:35 — Test a detection tradeoff

Open **Detections → APP-002**.

**Local path:** change **Threshold** from **1000** to **1500**. Enter the proposal
reason `Compare benign reconciliation against required access signals.` Click
**Save proposal**, then **Run corpus comparison**. Inspect the computed **PASS**
gate, parameter diff, the bulk-automation row, and the service-access row.

> This removes the benign reconciliation signal while retaining the two required
> volume detections. TP/FN count required scenarios; FP/TN count explicitly benign
> scenarios. Other scenarios still participate in the regression gates. These
> are synthetic fixture measurements, not production precision or recall.

Enter **Review reason**: `Reviewed all scenario obligations and the correlation outcomes.`
Click **Approve revision**. Explain that approval independently recomputes the
comparison and checks the current baseline. Reload to show the saved review.

> Approved local rules affect subsequent replays. They do not rewrite the
> original Atlas alerts or evidence. A blocking result cannot be approved; WARN
> requires deliberate review and does not establish improvement.

**Public alternative:** choose **1,500 records** to inspect the same shipped-rule
comparison. Then choose **2,200 records** and show **BLOCK**: the service-principal
volume signal and its correlated incident are lost. No editable fields or approval
actions are available publicly. The **1,100 records** example demonstrates WARN
with unchanged fixture outcomes if there is time.

## 05:35–06:10 — Inspect measured obligations

Open **Evaluations → V2 analyst benchmark**. Read the executed counts from the
screen, select a citation or false-premise category, and expand one obligation's
**Expected behavior** and **Observed result**. Point to its metric definition and
denominator.

> These are named application-boundary obligations executed against synthetic
> fixtures. Their populations overlap, so I do not add the denominators together.
> The original boundary suite and historical live OpenAI record are separate.
> Passing these cases is not a model accuracy or universal injection-resistance
> claim.

Use [current validation](VALIDATION.md) for the actual test and CI results rather
than memorizing a count that may change.

## 06:10–07:00 — Export, verify, and state the limit

Return to the canonical Atlas case's **Export** tab. Click **Download evidence
bundle**. Show **VALID**, then expand **Inspect declared files and SHA-256 hashes**.
Select that download with **Verify a local bundle** to repeat verification in the
browser. The selected file is not uploaded or extracted.

> This captures a bounded committed snapshot with exact UTF-8 content hashes.
> Public exports omit local human annotations, findings, notes, audit records,
> and saved reviews. Local exports include bounded committed review material.

> VALID means the contents match this manifest. The manifest is unsigned and can
> be replaced along with the files; hashes do not prove authorship, source truth,
> or legal chain of custody. Authentication, tenant isolation, independent
> retention, and measured production operations remain future work.

The same downloaded file can be checked offline with:

```sh
python -m aegisgraph.cli verify-bundle bundle.json
```

Use the actual downloaded filename in place of `bundle.json`. After a local
rehearsal, a disposable reset restores the original rule baseline and removes the
saved demo actions. Stop the demo API before that reset.

## Follow-up paths and recovery

For more time, compare the approved-administration and mixed-context scenarios,
record a local hypothesis review, demonstrate report-approval invalidation, or
inspect a deliberately modified copy of an export. Keep original and modified
files distinct; changing content without its manifest should show **MODIFIED**.

If a dependency is unavailable, use `demo-health`, the visible request ID, and
[setup](SETUP.md). Continue with the explicitly deterministic local demo when
appropriate. [Reviewed screenshots](screenshots/README.md) document recorded
views; label them as recordings rather than pretending they are a live session.
