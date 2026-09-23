"use client";
import { useState } from "react";
import type { AnalystBenchmark } from "@/lib/benchmark-types";
import { humanize } from "@/lib/format";
import { Badge, Panel } from "./ui";

export function BenchmarkResults({ run }: { run: AnalystBenchmark }) {
  const [category, setCategory] = useState("");
  const [result, setResult] = useState("all");
  const categories = [...new Set(run.cases.map((item) => item.category))];
  const cases = run.cases.filter(
    (item) =>
      (!category || item.category === category) &&
      (result === "all" || item.passed === (result === "passed")),
  );
  return (
    <>
      <p className="notice">
        {run.scope} No live model is called. These are synthetic fixture
        obligations, not measured real-world AI accuracy or security guarantees.
      </p>
      <div className="eval-metrics">
        {[
          { label: "Executed obligations", value: run.total },
          { label: "Passed", value: run.passed },
          { label: "Failed", value: run.failed },
        ].map((item) => (
          <div className="metric" key={item.label}>
            <div className="metric-top">{item.label}</div>
            <div className="metric-value">{item.value}</div>
            <small>Fixture version {run.fixture_version} · deterministic</small>
          </div>
        ))}
      </div>
      <Panel
        title="Defined metric populations"
        subtitle="Each denominator counts named obligations assigned to that metric."
      >
        <div className="benchmark-metrics">
          {run.metrics.map((metric) => (
            <article key={metric.id}>
              <h3>{metric.label}</h3>
              <strong>
                {metric.passed} / {metric.total}
              </strong>
              <p>{metric.definition}</p>
            </article>
          ))}
        </div>
        <p className="panel-body page-note">
          Metric populations overlap. Their denominators must not be added
          together. Unsupported factual claims and malformed schemas are tested
          separately.
        </p>
      </Panel>
      <Panel
        title="Benchmark obligations"
        className="mt-6"
        subtitle="Expected and observed behavior from the executed fixture runner"
      >
        <div className="toolbar">
          <div className="form-field filter-field">
            <label htmlFor="benchmark-category">Benchmark category</label>
            <select
              id="benchmark-category"
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
          <div className="form-field filter-field">
            <label htmlFor="benchmark-result">Benchmark result</label>
            <select
              id="benchmark-result"
              value={result}
              onChange={(e) => setResult(e.target.value)}
            >
              <option value="all">All results</option>
              <option value="failed">Failed</option>
              <option value="passed">Passed</option>
            </select>
          </div>
          <span className="page-note">
            Showing {cases.length} of {run.total}
          </span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Obligation</th>
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
                          <dd>
                            <pre className="benchmark-output">
                              {JSON.stringify(item.expected, null, 2)}
                            </pre>
                          </dd>
                        </div>
                        <div>
                          <dt>Observed result</dt>
                          <dd>
                            <pre className="benchmark-output">
                              {JSON.stringify(item.actual, null, 2)}
                            </pre>
                          </dd>
                        </div>
                      </dl>
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
        {cases.length === 0 && (
          <p className="panel-body">No obligations match these filters.</p>
        )}
      </Panel>
      <details className="source-details benchmark-provenance">
        <summary>Fixture and ruleset provenance</summary>
        <p className="page-note">
          Format {run.format_version} · fixture {run.fixture_version}. This
          process caches one reproducible baseline run; local rule proposals use
          the separate detection regression workbench.
        </p>
        <dl>
          {Object.entries(run.provenance).map(([key, value]) => (
            <div key={key}>
              <dt>{humanize(key)}</dt>
              <dd className="mono">{value}</dd>
            </div>
          ))}
        </dl>
      </details>
    </>
  );
}
