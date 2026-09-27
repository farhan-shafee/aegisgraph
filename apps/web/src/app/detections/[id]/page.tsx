import Link from "next/link";
import { notFound } from "next/navigation";
import { DetectionWorkbench } from "@/components/detection-workbench";
import { PageHeading, Panel } from "@/components/ui";
import { ApiError } from "@/lib/api";
import type { DetectionWorkbenchData } from "@/lib/detection-types";
import { serverApi } from "@/lib/server-api";
import { checkedFrontendConfig } from "@/lib/server-runtime";

export const dynamic = "force-dynamic";

export default async function DetectionPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ comparison?: string | string[] }>;
}) {
  const { id } = await params;
  if (!/^[A-Z]{2,4}-[0-9]{3}$/.test(id)) notFound();
  let initial: DetectionWorkbenchData | null = null;
  let available = false;
  let failed = false;
  try {
    const configuration = await checkedFrontendConfig();
    available = configuration.capabilities.rule_workbench === 1;
    if (available) {
      initial = await serverApi<DetectionWorkbenchData>(
        `/detections/${id}/workbench`,
      );
    }
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    failed = true;
  }
  if (!available && !failed) {
    return (
      <>
        <PageHeading
          eyebrow="DETECTION ENGINEERING"
          title="Detection workbench"
          description="The connected service does not yet advertise this feature."
        />
        <Panel title="Rule inspection remains available">
          <div className="panel-body">
            <Link className="text-link" href="/detections">
              Return to the rule library
            </Link>
          </div>
        </Panel>
      </>
    );
  }
  if (!initial) {
    return (
      <>
        <PageHeading
          eyebrow="DETECTION ENGINEERING"
          title="Rule unavailable"
          description="The workbench could not be loaded. Try this rule again when the service is available."
        />
        <Panel title="Continue inspecting the rules">
          <div className="panel-body">
            <Link className="text-link" href="/detections">
              Return to the rule library
            </Link>
          </div>
        </Panel>
      </>
    );
  }
  const query = await searchParams;
  const comparison =
    typeof query?.comparison === "string" && query.comparison.length <= 32
      ? query.comparison
      : undefined;
  return (
    <DetectionWorkbench
      key={`${id}:${comparison ?? "default"}`}
      initial={initial}
      initialComparison={comparison}
    />
  );
}
