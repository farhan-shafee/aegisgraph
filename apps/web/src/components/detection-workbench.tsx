"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { dateTime, humanize } from "@/lib/format";
import type {
  DetectionWorkbenchData,
  RegressionResult,
  RegressionRun,
  RevisionDetail,
  RuleRevision,
} from "@/lib/detection-types";
import { useCapability, usePublicDemo } from "./demo-mode";
import { Badge, ErrorNotice, PageHeading, Panel } from "./ui";
import styles from "./detection-workbench.module.css";

const examples = [
  {
    id: "reduce-benign-volume",
    label: "1,500 records",
    description: "Reduce benign volume alerts",
  },
  {
    id: "unchanged-volume",
    label: "1,100 records",
    description: "Inspect unchanged outcomes",
  },
  {
    id: "miss-service-access",
    label: "2,200 records",
    description: "Inspect a missed required signal",
  },
];

function parameterValues(data: DetectionWorkbenchData) {
  return Object.fromEntries(
    data.parameters.map((parameter) => [
      parameter.name,
      String(parameter.value),
    ]),
  );
}

function Gate({
  decision,
}: {
  decision: RegressionResult["gate"]["decision"];
}) {
  return (
    <Badge
      value={
        decision === "PASS" ? "low" : decision === "WARN" ? "medium" : "high"
      }
    >
      {decision}
    </Badge>
  );
}

export function RegressionComparison({ result }: { result: RegressionResult }) {
  const { before, after } = result.metrics;
  return (
    <Panel
      title="Corpus comparison"
      subtitle="Complete ruleset before and after the proposed change"
      action={<Gate decision={result.gate.decision} />}
    >
      <div className={styles.body}>
        <div className={styles.changes}>
          {result.parameter_changes.map((change) => (
            <p key={change.parameter}>
              <strong>{humanize(change.parameter)}</strong>
              <span className="mono">
                {change.before.toLocaleString("en-US")} →{" "}
                {change.after.toLocaleString("en-US")}
              </span>
            </p>
          ))}
        </div>
        <ul className={styles.reasons}>
          {result.gate.reasons.map((reason, index) => (
            <li key={`${reason.code}-${index}`}>{reason.message}</li>
          ))}
        </ul>
        <div className="eyebrow">SYNTHETIC FIXTURE MEASUREMENTS</div>
        <p className={styles.muted}>
          These results describe this corpus. They do not estimate production
          detection accuracy or provide a security guarantee.
        </p>
        <div
          className={styles.tableRegion}
          role="region"
          aria-label="Selected-rule fixture measurements"
          tabIndex={0}
        >
          <table className={styles.metricTable}>
            <caption>Selected rule: {result.selected_rule_id}</caption>
            <thead>
              <tr>
                <th scope="col">Measurement</th>
                <th scope="col">Before</th>
                <th scope="col">After</th>
              </tr>
            </thead>
            <tbody>
              {(
                [
                  ["tp", "TP · required scenario matched"],
                  ["fn", "FN · required scenario missed"],
                  ["fp", "FP · benign scenario matched"],
                  ["tn", "TN · benign scenario not matched"],
                ] as const
              ).map(([key, label]) => (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  <td>{before.selected_rule[key]}</td>
                  <td>{after.selected_rule[key]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className={styles.populations}>
          <p>
            <strong>
              {after.selected_rule_required_scenarios} required scenarios
            </strong>
            <span>Population for TP / FN</span>
          </p>
          <p>
            <strong>
              {after.selected_rule_benign_scenarios} benign scenarios
            </strong>
            <span>Population for FP / TN</span>
          </p>
          <p>
            <strong>
              {after.selected_rule_other_scenarios} other scenarios
            </strong>
            <span>Excluded from this matrix; retained in regression gates</span>
          </p>
        </div>
        <p>
          Required scenario-rule matches:{" "}
          <strong>
            {before.required_detection_hits}/{before.required_detection_total} →{" "}
            {after.required_detection_hits}/{after.required_detection_total}
          </strong>
          . Benign-fixture alerts across all rules:{" "}
          <strong>
            {before.benign_alert_count} → {after.benign_alert_count}
          </strong>
          . New regression violations:{" "}
          <strong>{result.regression_count}</strong>.
        </p>
        <div
          className={styles.tableRegion}
          role="region"
          aria-label="Scenario signal and correlation differences"
          tabIndex={0}
        >
          <table className={styles.scenarioTable}>
            <caption>
              All scenarios · signal counts and correlated incidents
            </caption>
            <thead>
              <tr>
                <th scope="col">Scenario</th>
                <th scope="col">Signals</th>
                <th scope="col">Incidents</th>
                <th scope="col">Rule changes / obligations</th>
              </tr>
            </thead>
            <tbody>
              {result.scenarios.map((scenario) => (
                <tr key={scenario.scenario_id}>
                  <th scope="row">
                    <Link
                      className="text-link"
                      href={`/replay?scenario=${encodeURIComponent(scenario.scenario_id)}`}
                    >
                      {humanize(scenario.scenario_id)}
                    </Link>
                    <small className={styles.block}>
                      {humanize(scenario.classification)} fixture
                    </small>
                  </th>
                  <td>
                    {scenario.before.alert_count} → {scenario.after.alert_count}
                  </td>
                  <td>
                    {scenario.before.incident_count} →{" "}
                    {scenario.after.incident_count}
                    <small className={styles.block}>
                      Expected {scenario.expected_incident_count}
                    </small>
                  </td>
                  <td>
                    <p>
                      {scenario.added_rule_ids.length
                        ? `Added: ${scenario.added_rule_ids.join(", ")}`
                        : "No added rules"}
                    </p>
                    <p>
                      {scenario.removed_rule_ids.length
                        ? `Removed: ${scenario.removed_rule_ids.join(", ")}`
                        : "No removed rules"}
                    </p>
                    {scenario.after.missed_required_rule_ids.length > 0 && (
                      <p className={styles.danger}>
                        Missing required:{" "}
                        {scenario.after.missed_required_rule_ids.join(", ")}
                      </p>
                    )}
                    {scenario.after.forbidden_rule_ids.length > 0 && (
                      <p className={styles.danger}>
                        Forbidden:{" "}
                        {scenario.after.forbidden_rule_ids.join(", ")}
                      </p>
                    )}
                    {!scenario.after.correlation_matches && (
                      <p className={styles.danger}>
                        Correlation obligation failed
                      </p>
                    )}
                    <details className={styles.details}>
                      <summary>Inspect rule matches</summary>
                      <p>
                        Before:{" "}
                        {Object.entries(scenario.before.rule_match_counts)
                          .map(([id, count]) => `${id} (${count})`)
                          .join(", ") || "None"}
                      </p>
                      <p>
                        After:{" "}
                        {Object.entries(scenario.after.rule_match_counts)
                          .map(([id, count]) => `${id} (${count})`)
                          .join(", ") || "None"}
                      </p>
                      <p>
                        Required:{" "}
                        {scenario.required_rule_ids.join(", ") || "None"}
                      </p>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <details className={styles.details}>
          <summary>Comparison provenance</summary>
          <dl className={styles.digests}>
            <dt>Corpus SHA-256</dt>
            <dd>{result.corpus_digest}</dd>
            <dt>Baseline ruleset SHA-256</dt>
            <dd>{result.baseline_ruleset_digest}</dd>
            <dt>Proposed ruleset SHA-256</dt>
            <dd>{result.proposed_ruleset_digest}</dd>
          </dl>
        </details>
      </div>
    </Panel>
  );
}

export function DetectionWorkbench({
  initial,
}: {
  initial: DetectionWorkbenchData;
}) {
  const capability = useCapability("rule_workbench");
  const publicDemo = usePublicDemo();
  const [workbench, setWorkbench] = useState(initial);
  const readOnly = publicDemo || workbench.read_only;
  const [values, setValues] = useState(() => parameterValues(initial));
  const [proposalReason, setProposalReason] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const [warningAcknowledged, setWarningAcknowledged] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(
    initial.revisions[0]?.id || null,
  );
  const [detail, setDetail] = useState<RevisionDetail | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedExample, setSelectedExample] = useState<string | null>(null);
  const [example, setExample] = useState<RegressionResult | null>(null);
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!capability || readOnly || !selectedId) return;
    const controller = new AbortController();
    api<RevisionDetail>(
      `/detection-versions/${encodeURIComponent(selectedId)}`,
      { signal: controller.signal },
    )
      .then((data) => {
        if (!controller.signal.aborted) setDetail(data);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      });
    return () => controller.abort();
  }, [selectedId, readOnly, capability, retry]);

  useEffect(() => {
    if (!capability || !selectedExample) return;
    const controller = new AbortController();
    api<RegressionResult>(`/regressions/examples/${selectedExample}`, {
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setExample(data);
          setNotice(`Example comparison loaded: ${data.gate.decision}.`);
        }
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      });
    return () => controller.abort();
  }, [selectedExample, capability, retry]);

  const run =
    detail?.runs.find((item) => item.id === selectedRunId) || detail?.runs[0];
  const stale =
    conflict ||
    Boolean(
      detail?.revision.status === "proposed" &&
      (detail.revision.base_generation !== workbench.generation ||
        detail.revision.base_ruleset_digest !== workbench.ruleset_digest),
    );
  const validParameters = workbench.parameters.every((parameter) => {
    const input = values[parameter.name];
    const value = Number(input);
    return (
      input?.trim() !== "" &&
      Number.isSafeInteger(value) &&
      value >= parameter.minimum &&
      value <= parameter.maximum &&
      (value - parameter.minimum) % parameter.step === 0
    );
  });
  const changed = workbench.parameters.some(
    (parameter) => Number(values[parameter.name]) !== parameter.value,
  );

  function failed(failure: unknown) {
    setError(errorMessage(failure));
    if (failure instanceof ApiError && failure.status === 409)
      setConflict(true);
  }

  async function refresh() {
    setBusy("Refreshing workbench");
    setError(null);
    try {
      const latest = await api<DetectionWorkbenchData>(
        `/detections/${workbench.rule.id}/workbench`,
      );
      setWorkbench(latest);
      setValues(parameterValues(latest));
      setConflict(false);
      setDetail(null);
      setSelectedId(null);
      setSelectedRunId(null);
      setReviewReason("");
      setWarningAcknowledged(false);
      setNotice(
        "Workbench refreshed. Review the current parameters before creating a fresh proposal.",
      );
    } catch (failure) {
      failed(failure);
    } finally {
      setBusy(null);
    }
  }

  async function propose(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      readOnly ||
      !capability ||
      busy ||
      stale ||
      !validParameters ||
      !changed ||
      !proposalReason.trim()
    )
      return;
    setBusy("Saving proposal");
    setError(null);
    setNotice("");
    try {
      const proposed = await api<RuleRevision>(
        `/detections/${workbench.rule.id}/versions`,
        {
          method: "POST",
          body: JSON.stringify({
            parameters: Object.fromEntries(
              workbench.parameters.map((parameter) => [
                parameter.name,
                Number(values[parameter.name]),
              ]),
            ),
            base_ruleset_digest: workbench.ruleset_digest,
            base_generation: workbench.generation,
            base_version: workbench.version,
            reason: proposalReason.trim(),
          }),
        },
      );
      setWorkbench((current) => ({
        ...current,
        revisions: [proposed, ...current.revisions].slice(0, 20),
        revision_count: current.revision_count + 1,
      }));
      setDetail(null);
      setSelectedId(proposed.id);
      setSelectedRunId(null);
      setReviewReason("");
      setWarningAcknowledged(false);
      setNotice(
        `Revision ${proposed.version} saved. Run the corpus comparison before approval.`,
      );
    } catch (failure) {
      failed(failure);
    } finally {
      setBusy(null);
    }
  }

  async function compare() {
    if (
      readOnly ||
      !capability ||
      busy ||
      !detail ||
      detail.revision.status !== "proposed" ||
      stale
    )
      return;
    setBusy("Running corpus comparison");
    setError(null);
    setNotice("");
    try {
      const compared = await api<RegressionRun>(
        `/detection-versions/${detail.revision.id}/regressions`,
        { method: "POST" },
      );
      setDetail({ ...detail, runs: [compared, ...detail.runs] });
      setSelectedRunId(compared.id);
      setWarningAcknowledged(false);
      setNotice(
        `Corpus comparison complete: ${compared.result.gate.decision}. Inspect the scenarios before review.`,
      );
    } catch (failure) {
      failed(failure);
    } finally {
      setBusy(null);
    }
  }

  async function review(decision: "approve" | "reject") {
    if (
      readOnly ||
      !capability ||
      busy ||
      !detail ||
      detail.revision.status !== "proposed" ||
      !reviewReason.trim()
    )
      return;
    if (
      decision === "approve" &&
      (stale ||
        !run ||
        run.result.gate.decision === "BLOCK" ||
        (run.result.gate.decision === "WARN" && !warningAcknowledged))
    )
      return;
    setBusy(
      decision === "approve" ? "Approving revision" : "Rejecting revision",
    );
    setError(null);
    setNotice("");
    let recorded = false;
    try {
      await api(`/detection-versions/${detail.revision.id}/review`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          regression_id: run?.id || null,
          reason: reviewReason.trim(),
        }),
      });
      recorded = true;
      setDetail({
        ...detail,
        revision: {
          ...detail.revision,
          status: decision === "approve" ? "approved" : "rejected",
        },
      });
      const [latest, saved] = await Promise.all([
        api<DetectionWorkbenchData>(
          `/detections/${workbench.rule.id}/workbench`,
        ),
        api<RevisionDetail>(`/detection-versions/${detail.revision.id}`),
      ]);
      setWorkbench(latest);
      setValues(parameterValues(latest));
      setDetail(saved);
      setSelectedRunId(null);
      setConflict(false);
      setReviewReason("");
      setWarningAcknowledged(false);
      setNotice(
        decision === "approve"
          ? "Revision approved. Approved rules affect future replays; historical alerts remain unchanged."
          : "Revision rejected. The effective ruleset is unchanged.",
      );
    } catch (failure) {
      if (recorded) {
        setConflict(true);
        setError(
          "The decision was saved, but its refreshed details are unavailable. Refresh the workbench before making another change.",
        );
        setNotice(
          decision === "approve" ? "Revision approved." : "Revision rejected.",
        );
      } else {
        failed(failure);
      }
    } finally {
      setBusy(null);
    }
  }

  if (!capability)
    return (
      <Panel title="Detection workbench is not available">
        <div className={styles.body}>
          <p>The connected service does not yet advertise this feature.</p>
          <Link className="text-link" href="/detections">
            Return to the rule library
          </Link>
        </div>
      </Panel>
    );

  return (
    <div className={styles.workbench}>
      <Link href="/detections" className="text-link">
        ← Rule library
      </Link>
      <PageHeading
        eyebrow={`${workbench.rule.id} / DETECTION ENGINEERING`}
        title={workbench.rule.name}
        description={workbench.rule.description}
        action={<Badge value={workbench.rule.severity} />}
      />
      <ErrorNotice message={error} />
      <p role="status" aria-live="polite" className={styles.status}>
        {busy ? `${busy}…` : notice}
      </p>
      {error && (
        <div className={styles.actions}>
          {readOnly ? (
            <button
              className="button secondary"
              type="button"
              onClick={() => {
                setError(null);
                setRetry((value) => value + 1);
              }}
            >
              Retry comparison
            </button>
          ) : (
            <>
              <button
                className="button secondary"
                type="button"
                disabled={Boolean(busy)}
                onClick={refresh}
              >
                Refresh workbench
              </button>
              {selectedId && !detail && (
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => {
                    setError(null);
                    setRetry((value) => value + 1);
                  }}
                >
                  Retry revision history
                </button>
              )}
            </>
          )}
        </div>
      )}
      <Panel
        title={`Effective rule · version ${workbench.version}`}
        subtitle={
          readOnly
            ? "Repository baseline · read-only public demo"
            : "Local ruleset · human-reviewed revisions"
        }
      >
        <div className={styles.body}>
          <dl className={styles.parameters}>
            {workbench.parameters.map((parameter) => (
              <div key={parameter.name}>
                <dt>{parameter.label}</dt>
                <dd>
                  {parameter.value.toLocaleString("en-US")}
                  {parameter.name === "window_minutes" ? " min" : ""}
                </dd>
              </div>
            ))}
          </dl>
          {!workbench.parameters.length && (
            <p>
              This rule has no tunable parameters. Its fixed logic remains
              available in the rule library.
            </p>
          )}
          <p className={styles.muted}>
            Approved local revisions affect subsequent scenario replays. The
            canonical Atlas investigation and its historical alert counts are
            preserved.
          </p>
          <details className={styles.details}>
            <summary>Effective ruleset provenance</summary>
            <p>Generation {workbench.generation}</p>
            <p className={styles.digest}>{workbench.ruleset_digest}</p>
          </details>
        </div>
      </Panel>
      {readOnly ? (
        <Panel
          title="Explore the volume tradeoff"
          subtitle="Three fixed APP-002 comparisons, computed from the same synthetic corpus"
        >
          <div className={styles.body}>
            <p>
              Public mode cannot save proposals or approve changes. Each example
              compares the repository baseline against one bounded threshold.
            </p>
            {workbench.rule.id === "APP-002" ? (
              <div className={styles.exampleGrid}>
                {examples.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={styles.example}
                    aria-pressed={selectedExample === item.id}
                    onClick={() => {
                      setExample(null);
                      setSelectedExample(item.id);
                      setError(null);
                      if (item.id === selectedExample)
                        setRetry((value) => value + 1);
                    }}
                  >
                    <strong>{item.label}</strong>
                    <span>{item.description}</span>
                  </button>
                ))}
              </div>
            ) : (
              <Link href="/detections/APP-002" className="text-link">
                Inspect APP-002 threshold examples
              </Link>
            )}
            {selectedExample && !example && !error && (
              <p role="status">Computing fixture comparison…</p>
            )}
          </div>
        </Panel>
      ) : (
        <>
          {workbench.parameters.length > 0 && (
            <Panel
              title="1. Propose a revision"
              subtitle="Bounded integer parameters; saved proposals are immutable"
            >
              <form className={styles.body} onSubmit={propose}>
                <div className={styles.fields}>
                  {workbench.parameters.map((parameter) => (
                    <label key={parameter.name} className={styles.field}>
                      <span id={`parameter-${parameter.name}`}>
                        {parameter.label}
                      </span>
                      <input
                        aria-labelledby={`parameter-${parameter.name}`}
                        type="number"
                        min={parameter.minimum}
                        max={parameter.maximum}
                        step={parameter.step}
                        required
                        value={values[parameter.name] ?? ""}
                        onChange={(event) =>
                          setValues({
                            ...values,
                            [parameter.name]: event.target.value,
                          })
                        }
                        aria-describedby={`bounds-${parameter.name}`}
                      />
                      <small id={`bounds-${parameter.name}`}>
                        {parameter.minimum.toLocaleString("en-US")}–
                        {parameter.maximum.toLocaleString("en-US")} · current{" "}
                        {parameter.value.toLocaleString("en-US")}
                      </small>
                    </label>
                  ))}
                </div>
                <label className={styles.field}>
                  <span>Proposal reason</span>
                  <textarea
                    required
                    maxLength={1000}
                    rows={3}
                    value={proposalReason}
                    onChange={(event) => setProposalReason(event.target.value)}
                    placeholder="Explain the observed tradeoff and the change to evaluate."
                  />
                </label>
                <div className={styles.actions}>
                  <button
                    type="submit"
                    className="button primary"
                    disabled={
                      Boolean(busy) ||
                      stale ||
                      !validParameters ||
                      !changed ||
                      !proposalReason.trim()
                    }
                  >
                    Save proposal
                  </button>
                  {stale && !error && (
                    <button
                      type="button"
                      className="button secondary"
                      disabled={Boolean(busy)}
                      onClick={refresh}
                    >
                      Refresh workbench
                    </button>
                  )}
                </div>
                {stale && (
                  <p className={styles.warning}>
                    The saved baseline is stale or a workflow conflict occurred.
                    Refresh before proposing or approving changes.
                  </p>
                )}
              </form>
            </Panel>
          )}
          {workbench.revisions.length > 0 && (
            <Panel
              title="Revision history"
              subtitle={`Showing ${workbench.revisions.length} of ${workbench.revision_count} saved revisions`}
            >
              <div className={styles.history}>
                {workbench.revisions.map((item) => (
                  <button
                    type="button"
                    className={styles.historyItem}
                    key={item.id}
                    aria-pressed={selectedId === item.id}
                    disabled={Boolean(busy)}
                    onClick={() => {
                      setDetail(null);
                      setSelectedId(item.id);
                      setSelectedRunId(null);
                      setReviewReason("");
                      setWarningAcknowledged(false);
                      setError(null);
                      if (selectedId === item.id)
                        setRetry((value) => value + 1);
                    }}
                  >
                    <strong>
                      Version {item.version} · {humanize(item.status)}
                    </strong>
                    <span>{item.reason}</span>
                  </button>
                ))}
              </div>
              {selectedId && !detail && !error && (
                <p className={styles.body} role="status">
                  Loading revision and saved comparisons…
                </p>
              )}
            </Panel>
          )}
          {detail && (
            <Panel
              title={`2. Inspect revision ${detail.revision.version}`}
              subtitle={`Based on version ${detail.revision.parent_version} · ${detail.revision.status}`}
            >
              <div className={styles.body}>
                <p>{detail.revision.reason}</p>
                <p className={styles.muted}>
                  Proposed by {detail.revision.actor_label}. Local analyst
                  labels record attribution; they are not authenticated
                  identities.
                </p>
                <dl className={styles.parameters}>
                  {workbench.parameters.map((parameter) => (
                    <div key={parameter.name}>
                      <dt>Proposed {parameter.label.toLowerCase()}</dt>
                      <dd>
                        {detail.revision.snapshot[
                          parameter.name
                        ].toLocaleString("en-US")}
                      </dd>
                    </div>
                  ))}
                </dl>
                {detail.revision.status === "proposed" && (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={Boolean(busy) || stale || detail.runs.length >= 9}
                    onClick={compare}
                  >
                    Run corpus comparison
                  </button>
                )}
                {detail.runs.length >= 9 &&
                  detail.revision.status === "proposed" && (
                    <p className={styles.muted}>
                      The manual comparison limit has been reached for this
                      revision. One final run is reserved for approval.
                    </p>
                  )}
                {detail.runs.length > 1 && (
                  <label className={styles.field}>
                    <span>Saved comparison</span>
                    <select
                      value={run?.id || ""}
                      onChange={(event) => {
                        setSelectedRunId(event.target.value);
                        setWarningAcknowledged(false);
                      }}
                    >
                      {detail.runs.map((item, index) => (
                        <option key={item.id} value={item.id}>
                          {index === 0 ? "Latest" : `Earlier ${index}`} ·{" "}
                          {item.result.gate.decision} ·{" "}
                          {dateTime(item.created_at)}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {!detail.runs.length && (
                  <p className={styles.muted}>
                    No comparison has been recorded. Approval requires a
                    completed corpus run.
                  </p>
                )}
                {detail.review && (
                  <div className={styles.reviewRecord}>
                    <strong>
                      {detail.review.decision === "approve"
                        ? "Approved"
                        : "Rejected"}{" "}
                      by {detail.review.actor_label}
                    </strong>
                    <p>{detail.review.reason}</p>
                    <small>{dateTime(detail.review.created_at)}</small>
                  </div>
                )}
              </div>
            </Panel>
          )}
        </>
      )}
      {(readOnly ? example : run?.result) && (
        <RegressionComparison result={(readOnly ? example : run?.result)!} />
      )}
      {!readOnly && detail?.revision.status === "proposed" && (
        <Panel
          title="3. Record a human decision"
          subtitle="Approval recomputes the comparison and checks that its baseline is still current"
        >
          <div className={styles.body}>
            {run?.result.gate.decision === "BLOCK" && (
              <p className={styles.danger}>
                A blocking gate cannot be approved. Reject this revision or
                create a fresh proposal after reviewing the missed obligation.
              </p>
            )}
            {run?.result.gate.decision === "WARN" && (
              <label className={styles.acknowledge}>
                <input
                  type="checkbox"
                  checked={warningAcknowledged}
                  onChange={(event) =>
                    setWarningAcknowledged(event.target.checked)
                  }
                />
                <span>
                  I reviewed the warning and understand it does not establish a
                  measured improvement.
                </span>
              </label>
            )}
            <label className={styles.field}>
              <span>Review reason</span>
              <textarea
                rows={3}
                maxLength={1000}
                value={reviewReason}
                onChange={(event) => setReviewReason(event.target.value)}
                placeholder="Record why this outcome should be accepted or rejected."
              />
            </label>
            <div className={styles.actions}>
              <button
                className="button primary"
                type="button"
                disabled={
                  Boolean(busy) ||
                  stale ||
                  !run ||
                  !reviewReason.trim() ||
                  run.result.gate.decision === "BLOCK" ||
                  (run.result.gate.decision === "WARN" && !warningAcknowledged)
                }
                onClick={() => review("approve")}
              >
                Approve revision
              </button>
              <button
                className="button secondary"
                type="button"
                disabled={Boolean(busy) || !reviewReason.trim()}
                onClick={() => review("reject")}
              >
                Reject revision
              </button>
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}
