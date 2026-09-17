import type { LiveEvaluationRun } from "@/lib/types";
import { humanize } from "@/lib/format";
import { Badge, Empty, Panel } from "./ui";
export function LiveEvaluationResults({
  run,
}: {
  run: LiveEvaluationRun | null | undefined;
}) {
  if (!run || run.status === "not_run")
    return (
      <Panel className="live-validation">
        <Empty
          title={
            run
              ? "No live evaluation recorded"
              : "Live evaluation record unavailable"
          }
        >
          Live provider validation is run explicitly through the evaluation
          command. Opening this page does not call an external model.
        </Empty>
      </Panel>
    );
  return (
    <Panel
      className="live-validation"
      title="Live OpenAI validation"
      subtitle="Saved execution results · separate from deterministic fixtures"
      action={<Badge value={run.status} />}
    >
      <div className="panel-body">
        <p>
          {run.scope ||
            "This record separates real provider requests from application-boundary checks. Blocked or skipped requests are not successful model evaluations."}
        </p>
        <dl>
          <div>
            <dt>Live provider cases</dt>
            <dd>
              {run.live_cases
                ? `${run.live_cases.passed} passed / ${run.live_cases.total} cases`
                : "Not recorded"}
            </dd>
          </div>
          <div>
            <dt>Application boundary checks</dt>
            <dd>
              {run.boundary_cases
                ? `${run.boundary_cases.passed} passed / ${run.boundary_cases.total} checks`
                : "Not recorded"}
            </dd>
          </div>
          <div>
            <dt>Provider requests attempted</dt>
            <dd>{run.provider_requests_attempted ?? "Not recorded"}</dd>
          </div>
          <div>
            <dt>Request outcomes</dt>
            <dd>
              {run.provider_requests_succeeded !== undefined &&
              run.provider_requests_failed !== undefined
                ? `${run.provider_requests_succeeded} succeeded / ${run.provider_requests_failed} failed`
                : "Not recorded"}
            </dd>
          </div>
        </dl>
        <p className="page-note">
          Availability failures remain visible. Passing an individual real-model
          case does not establish general prompt-injection resistance.
        </p>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Case and evidence</th>
              <th>Execution</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {(run.cases || []).map((item) => (
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
                          {item.actual || item.detail || "No result recorded."}
                        </dd>
                      </div>
                    </dl>
                    {item.detail && item.detail !== item.actual && (
                      <p>{item.detail}</p>
                    )}
                  </details>
                </td>
                <td>{humanize(item.execution || "not recorded")}</td>
                <td>
                  <Badge
                    value={item.status || (item.passed ? "passed" : "failed")}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!!run.attempts?.length && (
        <details className="live-attempts">
          <summary>
            Provider request history ({run.attempts.length} attempts)
          </summary>
          <p>
            All saved attempts, including availability failures before a later
            success. HTTP 429 alone does not identify quota or rate-limit cause.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Attempt</th>
                  <th>Case</th>
                  <th>HTTP</th>
                  <th>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {run.attempts.map((attempt) => (
                  <tr key={attempt.attempt}>
                    <td>{attempt.attempt}</td>
                    <td>
                      <span className="rule-id">{attempt.case_id}</span>
                    </td>
                    <td>{attempt.http_status ?? "Not recorded"}</td>
                    <td>
                      {humanize(attempt.status)}
                      {attempt.safe_error && (
                        <small className="attempt-error">
                          {humanize(attempt.safe_error)}
                        </small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </Panel>
  );
}
