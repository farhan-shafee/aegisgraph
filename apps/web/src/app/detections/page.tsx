import { serverApi } from "@/lib/server-api";
import { checkedFrontendConfig } from "@/lib/server-runtime";
import Link from "next/link";
import type { Detection } from "@/lib/types";
import { Badge, Empty, PageHeading, Panel, Unavailable } from "@/components/ui";
import { humanize } from "@/lib/format";
export const dynamic = "force-dynamic";
export default async function DetectionsPage() {
  let data: { items: Detection[] };
  let workbenchAvailable = false;
  try {
    const [catalog, configuration] = await Promise.all([
      serverApi<{ items: Detection[] }>("/detections"),
      checkedFrontendConfig(),
    ]);
    data = catalog;
    workbenchAvailable = configuration.capabilities.rule_workbench === 1;
  } catch {
    return <Unavailable />;
  }
  return (
    <>
      <PageHeading
        eyebrow="DETECTION ENGINEERING"
        title="Detections"
        description="Versioned rules evaluate normalized events. Correlation gives those signals context."
      />
      {workbenchAvailable && (
        <Panel
          title="Inspect a threshold tradeoff"
          subtitle="From a typed parameter change to a measured regression gate"
        >
          <div className="panel-body">
            <p>
              Compare APP-002 against benign reconciliation and required
              service-access signals. Inspect the full corpus before deciding
              whether a change should be approved.
            </p>
            <Link href="/detections/APP-002" className="text-link">
              Open the volume rule workbench →
            </Link>
          </div>
        </Panel>
      )}
      <Panel
        title="Rule library"
        subtitle={`${data.items.length} detection definitions · alert counts describe canonical historical alerts`}
      >
        {data.items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Logic</th>
                  <th>Severity</th>
                  <th>Window</th>
                  <th>Historical alerts</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((rule) => (
                  <tr key={rule.id}>
                    <td>
                      {workbenchAvailable ? (
                        <Link
                          href={`/detections/${rule.id}`}
                          className="text-link rule-id"
                        >
                          {rule.id}
                        </Link>
                      ) : (
                        <span className="rule-id">{rule.id}</span>
                      )}
                      <br />
                      <strong>{rule.name}</strong>
                      <small className="rule-description">
                        {rule.description}
                      </small>
                    </td>
                    <td>{humanize(rule.kind)}</td>
                    <td>
                      <Badge value={rule.severity} />
                    </td>
                    <td className="mono">
                      {rule.window_minutes
                        ? `${rule.window_minutes} min`
                        : "Single event"}
                      {rule.threshold ? (
                        <small>Threshold ≥ {rule.threshold}</small>
                      ) : null}
                    </td>
                    <td>{rule.alert_count}</td>
                    <td>
                      <Badge value={rule.enabled ? "low" : "contained"}>
                        {rule.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="No rule definitions loaded" />
        )}
      </Panel>
    </>
  );
}
