import { serverApi } from "@/lib/server-api";
import type { Detection } from "@/lib/types";
import { Badge, Empty, PageHeading, Panel, Unavailable } from "@/components/ui";
import { humanize } from "@/lib/format";
export const dynamic = "force-dynamic";
export default async function DetectionsPage() {
  let data: { items: Detection[] };
  try {
    data = await serverApi("/detections");
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
      <Panel
        title="Rule library"
        subtitle={`${data.items.length} detection definitions · configuration stored as code`}
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
                  <th>Alerts</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((rule) => (
                  <tr key={rule.id}>
                    <td>
                      <span className="rule-id">{rule.id}</span>
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
