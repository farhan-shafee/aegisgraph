import { serverApi } from "@/lib/server-api";
import type { Incident } from "@/lib/types";
import { Unavailable } from "@/components/ui";
import { IncidentWorkspace } from "@/components/incident-workspace";
export const dynamic = "force-dynamic";
export default async function IncidentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let incident: Incident;
  try {
    incident = await serverApi<Incident>(
      `/incidents/${encodeURIComponent(id)}`,
    );
  } catch {
    return <Unavailable incident />;
  }
  return <IncidentWorkspace initial={incident} />;
}
