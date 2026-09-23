import Link from "next/link";
import { ScenarioReplay } from "@/components/scenario-replay";
import { PageHeading, Panel, Unavailable } from "@/components/ui";
import { serverApi } from "@/lib/server-api";
import { checkedFrontendConfig } from "@/lib/server-runtime";
import type { ScenarioDescription } from "@/lib/replay-types";

export default async function ReplayPage({
  searchParams,
}: {
  searchParams: Promise<{ scenario?: string | string[] }>;
}) {
  let config;
  try {
    config = await checkedFrontendConfig();
  } catch {
    return <Unavailable />;
  }
  const { capabilities } = config;
  if (capabilities.replay !== 1 || capabilities.scenarios !== 1)
    return (
      <>
        <PageHeading
          eyebrow="REPLAY"
          title="Scenario replay"
          description="Inspect the causal path from synthetic telemetry to a completed investigation."
        />
        <Panel title="Replay is unavailable on this backend version">
          <p className="page-note">
            The existing investigation is still available.
          </p>
          <Link className="button secondary" href="/incidents">
            Open investigations
          </Link>
        </Panel>
      </>
    );
  let data;
  try {
    data = await Promise.all([
      serverApi<{ items: ScenarioDescription[] }>("/scenarios"),
      searchParams,
    ]);
  } catch {
    return <Unavailable />;
  }
  const [{ items }, params] = data;
  return (
    <>
      <PageHeading
        eyebrow="REPLAY / SYNTHETIC CORPUS"
        title="Watch the evidence develop."
        description="Choose a scenario. Follow real detection and correlation decisions. Inspect every conclusion against its source."
      />
      <ScenarioReplay
        key={typeof params.scenario === "string" ? params.scenario : "default"}
        scenarios={items}
        initialScenarioId={
          typeof params.scenario === "string" ? params.scenario : undefined
        }
        hypothesesAvailable={capabilities.hypotheses === 1}
      />
    </>
  );
}
