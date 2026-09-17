"use client";
import { useState } from "react";
import { Play, ShieldCheck } from "lucide-react";
import type { EvaluationRun } from "@/lib/types";
import { api, errorMessage } from "@/lib/api";
import { dateTime, humanize } from "@/lib/format";
import { Badge, Empty, ErrorNotice, PageHeading, Panel } from "./ui";
export function EvaluationResults({
  initial,
}: {
  initial: EvaluationRun | null;
}) {
  const [run, setRun] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [category, setCategory] = useState("");
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
          <button className="button primary" disabled={busy} onClick={execute}>
            <Play size={14} />
            {busy ? "Running evaluation…" : "Run evaluation suite"}
          </button>
        }
      />
      <div className="notice">
        <ShieldCheck size={17} />
        <span>
          {run?.scope ||
            "Application boundary tests use deterministic and adversarial fixture providers. No external model is called."}{" "}
          These results describe the executed fixtures, not general model
          accuracy or production security.
        </span>
      </div>
      <div style={{ marginTop: error ? 15 : 0 }}>
        <ErrorNotice message={error} />
      </div>
      {run ? (
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
                          <p>
                            {item.detail ||
                              item.details ||
                              "No additional details recorded."}
                          </p>
                          {item.expected && <p>Expected: {item.expected}</p>}
                          {item.actual && <p>Observed: {item.actual}</p>}
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
