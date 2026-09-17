import { serverApi } from "@/lib/server-api";
import { ApiError } from "@/lib/api";
import type { EvaluationRun, LiveEvaluationRun } from "@/lib/types";
import { Unavailable } from "@/components/ui";
import { EvaluationResults } from "@/components/evaluation-results";
export const dynamic = "force-dynamic";
export default async function EvaluationsPage() {
  let data: EvaluationRun | null = null;
  const [deterministic, live] = await Promise.allSettled([
    serverApi<EvaluationRun | null>("/evaluations"),
    serverApi<LiveEvaluationRun>("/evaluations/live"),
  ]);
  if (deterministic.status === "fulfilled") data = deterministic.value;
  else {
    const error = deterministic.reason;
    if (!(error instanceof ApiError && error.status === 404))
      return <Unavailable />;
  }
  return (
    <EvaluationResults
      initial={data}
      live={live.status === "fulfilled" ? live.value : null}
    />
  );
}
