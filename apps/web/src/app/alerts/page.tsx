import { serverApi } from "@/lib/server-api";
import type { Alert, PageResult } from "@/lib/types";
import { PageHeading, Panel, Unavailable } from "@/components/ui";
import { AlertTable } from "@/components/data-tables";
export const dynamic = "force-dynamic";
export default async function AlertsPage() {
  let data: PageResult<Alert>;
  try {
    data = await serverApi("/alerts");
  } catch {
    return <Unavailable />;
  }
  return (
    <>
      <PageHeading
        eyebrow="DETECTION SIGNALS"
        title="Alerts"
        description="Individual suspicious signals and sequences, linked to source evidence."
      />
      <Panel
        title="Detection activity"
        subtitle={`${data.total} alerts from the stored telemetry`}
      >
        <AlertTable items={data.items} />
      </Panel>
      <p className="page-note">
        An alert is a signal, not a conclusion. Open its linked incident to
        assess the surrounding evidence.
      </p>
    </>
  );
}
