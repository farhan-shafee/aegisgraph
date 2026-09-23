"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  ArrowUpRight,
  Pause,
  Play,
  RotateCcw,
  SkipForward,
} from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { count, eventContext, eventLabel, humanize, time } from "@/lib/format";
import {
  frameDelay,
  replayPrefix,
  replaySpeeds,
  type ReplaySpeed,
} from "@/lib/replay-playback";
import type {
  ReplayFrame,
  ReplayProjection,
  ScenarioAnalysis,
  ScenarioDescription,
} from "@/lib/replay-types";
import type { Analysis, Evidence } from "@/lib/types";
import { Badge, Empty, ErrorNotice, Panel } from "./ui";
import { CitedText } from "./evidence-analyst";
import { EvidenceDrawer } from "./evidence-drawer";
import { HypothesisLedger } from "./hypothesis-ledger";
import styles from "./replay.module.css";

const stageLabels: Record<ReplayFrame["stage"], string> = {
  context_initialized: "Context initialized",
  telemetry: "Telemetry arrival",
  normalized: "Normalized event",
  rule_match: "Rule match",
  alert: "Alert emitted",
  correlation: "Correlation decision",
  incident: "Incident",
};
function subscribeMotion(callback: () => void) {
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}
const motionSnapshot = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const serverMotionSnapshot = () => false;

export function ScenarioReplay({
  scenarios,
  initialScenarioId,
  hypothesesAvailable = false,
}: {
  scenarios: ScenarioDescription[];
  initialScenarioId?: string;
  hypothesesAvailable?: boolean;
}) {
  const [selected, setSelected] = useState(
    scenarios.find((item) => item.id === initialScenarioId)?.id ??
      scenarios[0]?.id,
  );
  const scenario = scenarios.find((item) => item.id === selected);
  if (!scenario)
    return (
      <Empty title="No scenarios available">
        The canonical investigation remains available from Investigate.
      </Empty>
    );
  return (
    <div className={styles.root}>
      <Panel>
        <div className={styles.selector}>
          <div className="form-field">
            <label htmlFor="replay-scenario">Scenario</label>
            <select
              id="replay-scenario"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              {scenarios.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title} · {count(item.event_count)} events
                </option>
              ))}
            </select>
          </div>
          <span className="badge">
            Synthetic corpus · {scenarios.length} scenarios
          </span>
        </div>
        <div className={styles.description}>
          <div className="inline-meta">
            <Badge value={scenario.classification} />
            <span>Version {scenario.version}</span>
            <span>{count(scenario.event_count)} source events</span>
          </div>
          <h2>{scenario.title}</h2>
          <p>{scenario.purpose}</p>
          <p className={styles.muted}>Investigation theme: {scenario.theme}</p>
        </div>
        <details className={styles.catalog}>
          <summary>Browse scenario descriptions</summary>
          <div className={styles.catalogGrid}>
            {scenarios.map((item) => (
              <button
                type="button"
                key={item.id}
                className={styles.scenarioCard}
                aria-pressed={selected === item.id}
                onClick={() => setSelected(item.id)}
              >
                <strong>{item.title}</strong>
                <span>
                  {humanize(item.classification)} · {count(item.event_count)}{" "}
                  events
                </span>
                <p>{item.purpose}</p>
              </button>
            ))}
          </div>
        </details>
      </Panel>
      <ProjectionLoader
        key={scenario.id}
        scenario={scenario}
        hypothesesAvailable={hypothesesAvailable}
      />
    </div>
  );
}

function ProjectionLoader({
  scenario,
  hypothesesAvailable,
}: {
  scenario: ScenarioDescription;
  hypothesesAvailable: boolean;
}) {
  const [attempt, setAttempt] = useState(0);
  return (
    <ProjectionRequest
      key={attempt}
      scenario={scenario}
      hypothesesAvailable={hypothesesAvailable}
      retry={() => setAttempt((value) => value + 1)}
    />
  );
}

function ProjectionRequest({
  scenario,
  hypothesesAvailable,
  retry,
}: {
  scenario: ScenarioDescription;
  hypothesesAvailable: boolean;
  retry: () => void;
}) {
  const [projection, setProjection] = useState<ReplayProjection | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api<ReplayProjection>(`/replays/${encodeURIComponent(scenario.id)}`, {
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (
          result.format_version !== "1" ||
          result.provenance.scenario_id !== scenario.id ||
          result.provenance.scenario_version !== scenario.version ||
          result.frames.length !== result.summary.frame_count ||
          result.frames.length === 0
        ) {
          setError(
            "The replay projection is incompatible. Please reload after the service update.",
          );
          return;
        }
        setProjection(result);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(reason));
      });
    return () => controller.abort();
  }, [scenario.id, scenario.version]);
  if (error)
    return (
      <Panel title="Replay unavailable">
        <div className={styles.inset}>
          <ErrorNotice message={error} />
          <button type="button" className="button secondary" onClick={retry}>
            Retry replay
          </button>
        </div>
      </Panel>
    );
  if (!projection)
    return (
      <div className={styles.loading} role="status">
        Loading deterministic replay…
      </div>
    );
  return (
    <Playback
      projection={projection}
      scenario={scenario}
      hypothesesAvailable={hypothesesAvailable}
      reload={retry}
    />
  );
}

function Playback({
  projection,
  scenario,
  hypothesesAvailable,
  reload,
}: {
  projection: ReplayProjection;
  scenario: ScenarioDescription;
  hypothesesAvailable: boolean;
  reload: () => void;
}) {
  const [cursor, setCursor] = useState(0);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState<ReplaySpeed>(20);
  const reducedMotion = useSyncExternalStore(
    subscribeMotion,
    motionSnapshot,
    serverMotionSnapshot,
  );
  const complete = cursor === projection.frames.length;
  const status = complete
    ? "Replay complete"
    : running
      ? "Playing"
      : cursor
        ? "Paused"
        : "Ready to replay";
  const prefix = replayPrefix(
    projection.frames,
    cursor,
    projection.initial_state.event_count,
  );
  const current = prefix.frames.at(-1);
  useEffect(() => {
    if (!running || complete) return;
    const timer = window.setTimeout(
      () => setCursor((value) => value + 1),
      frameDelay(
        projection.frames[cursor - 1],
        projection.frames[cursor],
        speed,
      ),
    );
    return () => window.clearTimeout(timer);
  }, [running, complete, cursor, speed, projection]);
  function reset() {
    setRunning(false);
    setCursor(0);
  }
  return (
    <>
      <Panel
        title="Replay the investigation"
        subtitle="A browser cursor over a finite, causal projection. No fixture or case state is changed."
      >
        <div className={styles.controls}>
          <button
            type="button"
            className="button primary"
            disabled={complete}
            onClick={() => setRunning((value) => !value)}
          >
            {running && !complete ? (
              <Pause size={14} aria-hidden="true" />
            ) : (
              <Play size={14} aria-hidden="true" />
            )}
            {running && !complete
              ? "Pause"
              : cursor && !complete
                ? "Resume"
                : "Start"}
          </button>
          <button
            type="button"
            className="button secondary"
            disabled={complete}
            onClick={() => {
              setRunning(false);
              setCursor((value) =>
                Math.min(projection.frames.length, value + 1),
              );
            }}
          >
            <SkipForward size={14} aria-hidden="true" />
            Step
          </button>
          <button type="button" className="button secondary" onClick={reset}>
            <RotateCcw size={14} aria-hidden="true" />
            Reset
          </button>
          <label className={styles.speed}>
            Speed
            <select
              aria-label="Playback speed"
              value={speed}
              onChange={(event) =>
                setSpeed(Number(event.target.value) as ReplaySpeed)
              }
            >
              {replaySpeeds.map((value) => (
                <option key={value} value={value}>
                  {value}×
                </option>
              ))}
            </select>
          </label>
          <span
            className={styles.status}
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            {status}
          </span>
        </div>
        <div className={styles.progress}>
          <progress
            aria-label="Replay progress"
            value={cursor}
            max={projection.frames.length}
          />
          <div>
            <span>
              Frame {cursor} / {projection.frames.length}
            </span>
            <span>
              {current
                ? `${time(current.timestamp)} UTC · ${stageLabels[current.stage]}`
                : "Awaiting the first frame"}
            </span>
          </div>
        </div>
        <div className={styles.counts} aria-label="Reached replay state">
          <span>
            <strong>{count(prefix.eventCount)}</strong> source events received
          </span>
          <span>
            <strong>{prefix.alertCount}</strong> alerts emitted
          </span>
          <span>
            <strong>{prefix.incidentCount}</strong> correlated incidents
          </span>
        </div>
        <div className={styles.disclosure}>
          <p>
            Source-time gaps are divided by the selected speed, capped at 3
            seconds, with a 100 ms minimum per frame. Idle gaps are compressed;
            every frame is retained. Step advances exactly one frame.
          </p>
          {reducedMotion && (
            <p>
              Reduced motion: manual Step is available by default. Start
              explicitly enables timed playback.
            </p>
          )}
          {projection.summary.background_event_count > 0 && (
            <details>
              <summary>
                {count(projection.summary.background_event_count)} background
                records initialized before playback
              </summary>
              <p>
                These earlier normal records supply detector context and are
                folded from the frame log. The remaining{" "}
                {projection.summary.playback_event_count} observations are
                replayed in source order.
              </p>
            </details>
          )}
          <details>
            <summary>Projection provenance</summary>
            <dl>
              <dt>Scenario / version</dt>
              <dd>
                {projection.provenance.scenario_id} /{" "}
                {projection.provenance.scenario_version}
              </dd>
              <dt>Ruleset SHA-256</dt>
              <dd className={styles.digest}>
                {projection.provenance.ruleset_digest}
              </dd>
            </dl>
            <p>
              Public replay uses shipped rules. Local replay uses the approved
              rules at load time.
            </p>
            <button
              type="button"
              className="button ghost small"
              onClick={reload}
            >
              Reload rule snapshot
            </button>
          </details>
        </div>
      </Panel>
      <div className={styles.causalGrid}>
        <Panel
          title="Causal progression"
          subtitle="Latest reached frames · source time in UTC. Expand a frame to inspect its data."
        >
          {prefix.frames.length ? (
            <>
              <ol
                className={styles.frames}
                aria-label="Reached replay frames"
                onFocusCapture={() => setRunning(false)}
              >
                {prefix.frames.slice(-7).map((frame) => (
                  <FrameRow
                    key={frame.seq}
                    frame={frame}
                    current={frame.seq === current?.seq}
                  />
                ))}
              </ol>
              {prefix.frames.length > 7 && (
                <details
                  className={styles.history}
                  onFocusCapture={() => setRunning(false)}
                >
                  <summary>
                    Inspect all {prefix.frames.length} reached frames
                  </summary>
                  <ol
                    className={styles.frames}
                    aria-label="Full reached frame history"
                  >
                    {prefix.frames.map((frame) => (
                      <FrameRow key={frame.seq} frame={frame} current={false} />
                    ))}
                  </ol>
                </details>
              )}
            </>
          ) : (
            <Empty title="Ready for the first observation">
              Start playback or use Step to inspect each stage.
            </Empty>
          )}
        </Panel>
        <Panel
          title="Correlation state"
          subtitle="Based only on the reached prefix."
        >
          <div className={styles.inset}>
            {prefix.correlation ? (
              <>
                <p>
                  {prefix.correlation.rule_ids.length} distinct rules across{" "}
                  {prefix.correlation.rule_families.length} families have been
                  observed.
                </p>
                <p className={styles.muted}>
                  Policy: at least {prefix.correlation.minimum_rules} rules
                  across {prefix.correlation.minimum_families} families for a
                  principal within {prefix.correlation.window_minutes} minutes.
                </p>
                <p className={styles.muted}>
                  Observed rule totals alone do not prove one principal meets
                  the window.
                </p>
                {prefix.incidents.map((incident) => (
                  <div className={styles.incident} key={incident.id}>
                    <Badge value={incident.severity} />
                    <h3>{incident.title}</h3>
                    <p>{incident.summary}</p>
                    <span className="mono">{incident.id}</span>
                  </div>
                ))}
                {!prefix.incidents.length && (
                  <p>No correlated incident at this frame.</p>
                )}
              </>
            ) : (
              <p className={styles.muted}>
                No correlation decision has been reached.
              </p>
            )}
          </div>
        </Panel>
      </div>
      {complete ? (
        <CompletedInvestigation
          projection={projection}
          scenario={scenario}
          hypothesesAvailable={hypothesesAvailable}
        />
      ) : (
        <div className={styles.completionNote}>
          Complete the replay to inspect its evidence, hypotheses, and
          deterministic analyst answers.
        </div>
      )}
    </>
  );
}

function frameDescription(frame: ReplayFrame): string {
  switch (frame.stage) {
    case "context_initialized":
      return `${count(frame.data.event_count)} background records available`;
    case "telemetry":
      return `${humanize(frame.data.source)} · ${humanize(frame.data.event_type)}`;
    case "normalized":
      return eventLabel(frame.data.event);
    case "rule_match":
    case "alert":
      return `${frame.data.rule_id} · ${frame.data.rule_name}`;
    case "correlation":
      return `${frame.data.alert_count} alerts → ${frame.data.incident_count} correlated incidents`;
    case "incident":
      return `${humanize(frame.data.change)} · ${frame.data.incident.title}`;
  }
}
function FrameRow({
  frame,
  current,
}: {
  frame: ReplayFrame;
  current: boolean;
}) {
  return (
    <li className={styles.frame} aria-current={current ? "step" : undefined}>
      <details>
        <summary>
          <time dateTime={frame.timestamp}>{time(frame.timestamp)}</time>
          <span>
            <span className={styles.stage}>{stageLabels[frame.stage]}</span>
            <strong>{frameDescription(frame)}</strong>
          </span>
          <span className={styles.frameNumber}>#{frame.seq + 1}</span>
        </summary>
        <div className={styles.frameData}>
          {frame.event_id && <p className="mono">{frame.event_id}</p>}
          <pre>{JSON.stringify(frame.data, null, 2)}</pre>
        </div>
      </details>
    </li>
  );
}

function observedEntities(evidence: Evidence[]) {
  const entities = new Map<
    string,
    { kind: string; value: string; evidenceIds: string[] }
  >();
  for (const item of evidence) {
    const event = item.event;
    for (const [kind, value] of [
      ["Principal", event.actor?.user_id],
      ["Device", event.device?.device_id],
      ["Session", event.session?.session_id],
      ["Source IP", event.network?.source_ip],
      ["Resource", event.target?.resource_id],
    ] as const) {
      if (!value) continue;
      const key = `${kind}:${value}`;
      const row = entities.get(key) ?? { kind, value, evidenceIds: [] };
      row.evidenceIds.push(item.id);
      entities.set(key, row);
    }
  }
  return [...entities.values()];
}

function CompletedInvestigation({
  projection,
  scenario,
  hypothesesAvailable,
}: {
  projection: ReplayProjection;
  scenario: ScenarioDescription;
  hypothesesAvailable: boolean;
}) {
  const { investigation, alerts } = projection.final_state;
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(
    null,
  );
  const closeEvidence = useCallback(() => setSelectedEvidenceId(null), []);
  const selectedEvidence = investigation.evidence.find(
    (item) => item.id === selectedEvidenceId,
  );
  const entities = observedEntities(investigation.evidence);
  const drawerAlerts = alerts.map((alert) => ({
    ...alert,
    title: alert.rule_name,
  }));
  return (
    <div className={styles.completed}>
      <div className={styles.completedHeading}>
        <div>
          <div className="eyebrow">COMPLETED REPLAY</div>
          <h2>
            {investigation.kind === "observation_scope"
              ? "Observation scope"
              : "Correlated investigation"}
          </h2>
          <p className="mono">{investigation.id}</p>
        </div>
        {scenario.canonical_incident_id && (
          <Link
            className="button secondary"
            href={`/incidents/${encodeURIComponent(scenario.canonical_incident_id)}`}
          >
            Open canonical Atlas case
            <ArrowUpRight size={14} aria-hidden="true" />
          </Link>
        )}
      </div>
      <p className={styles.muted}>
        This completed projection is read-only and ephemeral.{" "}
        {investigation.kind === "observation_scope"
          ? "The observations did not produce a correlated incident."
          : "Its incident snapshot is the replay result."}{" "}
        {scenario.canonical_incident_id
          ? "The canonical Atlas case is a separate persisted investigation."
          : "There is no persisted case or analyst write workflow for this scenario."}
      </p>
      <div className={styles.resultGrid}>
        <Panel
          title="Completed evidence"
          subtitle={`${investigation.evidence.length} source events · chronological · inspect any citation`}
        >
          <ol className={styles.evidence}>
            {investigation.evidence.map((item) => (
              <li key={item.id}>
                <time dateTime={item.timestamp}>
                  {time(item.timestamp)} UTC
                </time>
                <h3>{eventLabel(item.event)}</h3>
                <p>{eventContext(item.event)}</p>
                <button
                  type="button"
                  className="evidence-citation"
                  onClick={() => setSelectedEvidenceId(item.id)}
                  aria-label={`Inspect evidence ${item.id}`}
                >
                  {item.id}
                </button>
              </li>
            ))}
          </ol>
        </Panel>
        <div className={styles.resultSide}>
          <Panel
            title="Emitted detections"
            subtitle={`${alerts.length} actual alerts from the replay`}
          >
            {alerts.length ? (
              <ul className={styles.alerts}>
                {alerts.map((alert) => (
                  <li key={alert.id}>
                    <Badge value={alert.severity} />
                    <h3>
                      {alert.rule_id} · {alert.rule_name}
                    </h3>
                    <p>{alert.description}</p>
                    <small>
                      {time(alert.timestamp)} UTC · {alert.event_ids.length}{" "}
                      supporting events
                    </small>
                    <div className="citation-group">
                      {investigation.evidence
                        .filter((item) =>
                          alert.event_ids.includes(item.event_id),
                        )
                        .map((item) => (
                          <button
                            type="button"
                            className="evidence-citation"
                            key={item.id}
                            onClick={() => setSelectedEvidenceId(item.id)}
                            aria-label={`Inspect alert evidence ${item.id}`}
                          >
                            {item.id}
                          </button>
                        ))}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty title="No alerts emitted">
                This ruleset produced no detection matches.
              </Empty>
            )}
          </Panel>
          <Panel
            title="Observed entities"
            subtitle="Values recorded in completed evidence; no identity attribution inferred."
          >
            <ul className={styles.entities}>
              {entities.map((entity) => (
                <li key={`${entity.kind}:${entity.value}`}>
                  <span>{entity.kind}</span>
                  <strong>{entity.value}</strong>
                  <details>
                    <summary>
                      {entity.evidenceIds.length} source citations
                    </summary>
                    <div className="citation-group">
                      {entity.evidenceIds.map((id) => (
                        <button
                          type="button"
                          className="evidence-citation"
                          key={id}
                          onClick={() => setSelectedEvidenceId(id)}
                          aria-label={`Inspect entity evidence ${id}`}
                        >
                          {id}
                        </button>
                      ))}
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
      {hypothesesAvailable ? (
        <>
          <HypothesisLedger
            endpoint={`/scenarios/${encodeURIComponent(scenario.id)}/hypotheses`}
            readOnly
            onEvidence={setSelectedEvidenceId}
            expectedProvenance={projection.provenance}
            expectedScopeId={investigation.id}
          />
          <ScenarioAnalyst
            projection={projection}
            onEvidence={setSelectedEvidenceId}
          />
        </>
      ) : (
        <p className={styles.completionNote}>
          Hypothesis and scenario analysis inspection is unavailable on this
          backend version.
        </p>
      )}
      {selectedEvidence && (
        <EvidenceDrawer
          key={selectedEvidence.id}
          evidence={selectedEvidence}
          alerts={drawerAlerts.filter((alert) =>
            alert.event_ids.includes(selectedEvidence.event_id),
          )}
          onClose={closeEvidence}
          readOnly
        />
      )}
    </div>
  );
}

const questions = [
  { id: "summary", text: "What most likely happened?" },
  { id: "malware", text: "What malware family was used?" },
] as const;
function ScenarioAnalyst({
  projection,
  onEvidence,
}: {
  projection: ReplayProjection;
  onEvidence: (id: string) => void;
}) {
  const [answer, setAnswer] = useState<Analysis | null>(null);
  const [asked, setAsked] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function ask(question: (typeof questions)[number]) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setAnswer(null);
    setError(null);
    setBusy(true);
    setAsked(question.text);
    try {
      const result = await api<ScenarioAnalysis>(
        `/scenarios/${encodeURIComponent(projection.provenance.scenario_id)}/analysis/${question.id}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      const provenance = result.provenance;
      if (
        result.scope_id !== projection.final_state.investigation.id ||
        provenance.scenario_id !== projection.provenance.scenario_id ||
        provenance.scenario_version !==
          projection.provenance.scenario_version ||
        provenance.ruleset_digest !== projection.provenance.ruleset_digest
      )
        throw new Error(
          "The scenario rules have changed. Reload the rule snapshot and replay before requesting analysis.",
        );
      setAnswer(result.analysis);
    } catch (reason) {
      if (!controller.signal.aborted) setError(errorMessage(reason));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  const evidenceIds = new Set(
    projection.final_state.investigation.evidence.map((item) => item.id),
  );
  const allowedIds = new Set(
    answer?.findings
      .flatMap((finding) => finding.evidence_ids)
      .filter((id) => evidenceIds.has(id)),
  );
  return (
    <Panel
      title="Evidence Analyst"
      subtitle="Two curated questions, bounded by the completed scenario evidence."
    >
      <div className={styles.inset}>
        <p className={styles.muted}>
          Answers use the deterministic provider in both modes, make no OpenAI
          requests, and do not create findings or change a case.
        </p>
        <div className={styles.questions}>
          {questions.map((question) => (
            <button
              type="button"
              className="button secondary"
              key={question.id}
              disabled={busy}
              onClick={() => void ask(question)}
            >
              {question.text}
              <ArrowUpRight size={13} aria-hidden="true" />
            </button>
          ))}
        </div>
        {busy && <p role="status">Checking the completed evidence…</p>}
        <ErrorNotice message={error} />
        {answer && (
          <section
            className={styles.answer}
            aria-label="Scenario analyst answer"
          >
            <Badge value={answer.status} />
            <h3>{asked}</h3>
            <p>
              <CitedText
                text={answer.summary}
                allowedIds={allowedIds}
                onEvidence={onEvidence}
              />
            </p>
            {answer.context_notice && (
              <p className="notice warning">{answer.context_notice}</p>
            )}
            {answer.findings.length > 0 && (
              <>
                <h3>Evidence-backed findings</h3>
                <ul className={styles.findings}>
                  {answer.findings.map((finding, index) => (
                    <li key={index}>
                      <p>{finding.statement}</p>
                      <div className="citation-group">
                        {finding.evidence_ids
                          .filter((id) => allowedIds.has(id))
                          .map((id) => (
                            <button
                              type="button"
                              key={id}
                              className="evidence-citation"
                              aria-label={`Inspect analyst evidence ${id}`}
                              onClick={() => onEvidence(id)}
                            >
                              {id}
                            </button>
                          ))}
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {answer.missing_evidence.length > 0 && (
              <>
                <h3>Facts not established / missing evidence</h3>
                <ul className="compact-list">
                  {answer.missing_evidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            )}
            {answer.recommended_next_steps.length > 0 && (
              <>
                <h3>What to inspect next</h3>
                <ul className="compact-list">
                  {answer.recommended_next_steps.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            )}
            <ErrorNotice message={answer.validation_errors.join(" ") || null} />
            <p className={styles.muted}>
              Provider: {answer.provider} · {answer.context_evidence_count}{" "}
              retrieved evidence items. Analyst review remains necessary.
            </p>
          </section>
        )}
      </div>
    </Panel>
  );
}
