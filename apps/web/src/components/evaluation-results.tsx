"use client";
import { useState } from "react";
import { Play, ShieldCheck } from "lucide-react";
import type { EvaluationRun, LiveEvaluationRun } from "@/lib/types";
import { api, errorMessage } from "@/lib/api";
import { dateTime, humanize } from "@/lib/format";
import { Badge, Empty, ErrorNotice, PageHeading, Panel } from "./ui";
import { LiveEvaluationResults } from "./live-evaluation-results";
export function EvaluationResults({
  initial,
  live,
}: {
  initial: EvaluationRun | null;
  live?: LiveEvaluationRun | null;
}) {
  const [run, setRun] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [category, setCategory] = useState("");
  const [view, setView] = useState<"deterministic" | "live">("deterministic");
  async function execute() {
    setBusy(true);
    setError(null);
    try {
      setRun(await api<EvaluationRun>("/evaluations/run", { method: "POST" }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  const categories = run
    ? [...new Set(run.cases.map((item) => item.category))]
    : [];
  const cases =
    run?.cases.filter((item) => !category || item.category === category) || [];
  return (
    <>
      <PageHeading
        eyebrow="SYSTEM ASSURANCE"
        title="AI & security evaluations"
        description="Executed tests of the evidence boundary, structured output, and unsupported claims."
        action={
          view === "deterministic" && (
            <button
              className="button primary"
              disabled={busy}
              onClick={execute}
            >
              <Play size={14} />
              {busy ? "Running evaluation…" : "Run deterministic suite"}
            </button>
          )
        }
      />
      <div className="evaluation-views" aria-label="Evaluation result sources">
        <button
          aria-pressed={view === "deterministic"}
          onClick={() => setView("deterministic")}
        >
          Deterministic boundary suite
        </button>
        <button aria-pressed={view === "live"} onClick={() => setView("live")}>
          Live OpenAI validation{" "}
          {live?.status && live.status !== "not_run" && (
            <Badge value={live.status} />
          )}
        </button>
      </div>
      {view === "deterministic" && (
        <div className="notice">
          <ShieldCheck size={17} />
          <span>
            {run?.scope ||
              "Application boundary tests use deterministic and adversarial fixture providers. No external model is called."}{" "}
            These results describe the executed fixtures, not general model
            accuracy or production security.
          </span>
        </div>
      )}
      <div style={{ marginTop: error ? 15 : 0 }}>
        <ErrorNotice message={error} />
      </div>
      {view === "live" ? (
        <LiveEvaluationResults run={live} />
      ) : run ? (
        <>
          <div className="eval-metrics">
            {[
              {
                label: "Executed cases",
                value: run.total,
                note: "Latest saved run",
              },
              {
                label: "Passed",
                value: run.passed,
                note: "Assertions satisfied",
              },
              {
                label: "Failed",
                value: run.failed,
                note: "Require investigation",
              },
            ].map((item) => (
              <div className="metric" key={item.label}>
                <div className="metric-top">{item.label}</div>
                <div
                  className="metric-value"
                  style={{
                    color: item.label === "Passed" ? "var(--teal)" : undefined,
                  }}
                >
                  {item.value}
                </div>
                <small>{item.note}</small>
              </div>
            ))}
          </div>
          <div
            className="eval-category-grid"
            aria-label="Measured category results"
          >
            {categories.map((item) => {
              const categoryCases = run.cases.filter(
                (test) => test.category === item,
              );
              return (
                <button
                  className="eval-category-button"
                  key={item}
                  aria-pressed={category === item}
                  onClick={() => setCategory(category === item ? "" : item)}
                >
                  <strong>{humanize(item)}</strong>
                  <span>
                    {categoryCases.filter((test) => test.passed).length} passed
                    · {categoryCases.filter((test) => !test.passed).length}{" "}
                    failed · {categoryCases.length} cases
                  </span>
                </button>
              );
            })}
          </div>
          <Panel
            title="Case results"
            subtitle={`Provider: ${run.provider || "deterministic"} · ${dateTime(run.completed_at || run.created_at || run.executed_at || "")}`}
          >
            <div className="toolbar">
              <div className="form-field filter-field">
                <label htmlFor="evaluation-category">Evaluation category</label>
                <select
                  id="evaluation-category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="">All categories</option>
                  {categories.map((item) => (
                    <option key={item} value={item}>
                      {humanize(item)}
                    </option>
                  ))}
                </select>
              </div>
              <span className="page-note">
                Showing {cases.length} of {run.total} executed cases
              </span>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Category</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <span className="rule-id">{item.id}</span>
                        <details className="evaluation-detail">
                          <summary>{item.name}</summary>
                          <dl className="case-expectation">
                            <div>
                              <dt>Expected behavior</dt>
                              <dd>{item.expected || item.name}</dd>
                            </div>
                            <div>
                              <dt>Observed result</dt>
                              <dd>
                                {item.actual ||
                                  item.detail ||
                                  item.details ||
                                  (item.passed
                                    ? "The executed assertions passed."
                                    : "The executed assertions failed.")}
                              </dd>
                            </div>
                          </dl>
                          {item.actual &&
                            item.detail &&
                            item.actual !== item.detail && <p>{item.detail}</p>}
                        </details>
                      </td>
                      <td>{humanize(item.category)}</td>
                      <td>
                        <Badge value={item.passed ? "passed" : "failed"} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <p className="page-note">
            Run {run.id || run.run_id}. Results are persisted by the API and
            recalculated when you execute the suite.
          </p>
        </>
      ) : (
        <Panel className="mt-6">
          <Empty title="No evaluation has been run">
            Run the suite to see actual case results. No scores are displayed
            before execution.
          </Empty>
        </Panel>
      )}
    </>
  );
}
