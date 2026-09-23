import { serverApi } from "@/lib/server-api";
import { ApiError } from "@/lib/api";
import type { EvaluationRun, LiveEvaluationRun } from "@/lib/types";
import { Unavailable } from "@/components/ui";
import { EvaluationResults } from "@/components/evaluation-results";
import { checkedFrontendConfig } from "@/lib/server-runtime";
import type { AnalystBenchmark } from "@/lib/benchmark-types";
export const dynamic = "force-dynamic";
export default async function EvaluationsPage() {
  let data: EvaluationRun | null = null;
  const { capabilities } = await checkedFrontendConfig();
  const [deterministic, live, benchmark] = await Promise.allSettled([
    serverApi<EvaluationRun | null>("/evaluations"),
    serverApi<LiveEvaluationRun>("/evaluations/live"),
    capabilities.analyst_benchmark === 1
      ? serverApi<AnalystBenchmark>("/evaluations/benchmark")
      : Promise.resolve(null),
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
      benchmark={benchmark.status === "fulfilled" ? benchmark.value : null}
      benchmarkError={
        benchmark.status === "rejected"
          ? "The V2 benchmark could not be loaded. Reload this page to retry; no score is shown for an unavailable run."
          : undefined
      }
    />
  );
}
