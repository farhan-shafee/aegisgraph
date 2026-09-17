import { serverApi } from "@/lib/server-api";
import type { Incident, PageResult } from "@/lib/types";
import { PageHeading, Panel, Unavailable } from "@/components/ui";
import { IncidentTable } from "@/components/data-tables";
export const dynamic = "force-dynamic";
export default async function IncidentsPage() {
  let data: PageResult<Incident>;
  try {
    data = await serverApi("/incidents");
  } catch {
    return <Unavailable />;
  }
  return (
    <>
      <PageHeading
        eyebrow="INVESTIGATE"
        title="Incident queue"
        description="Related signals, organized into bounded investigations."
      />
      <Panel
        title="All incidents"
        subtitle={`${data.total} incidents · deterministic correlation`}
      >
        <IncidentTable items={data.items} />
      </Panel>
      <p className="page-note">
        Incidents correlate shared identities and related alerts within a
        defined time window. Severity and status remain analyst decisions.
      </p>
    </>
  );
}
