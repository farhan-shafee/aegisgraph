import { serverApi } from "@/lib/server-api";
import { ApiError } from "@/lib/api";
import type { EvaluationRun } from "@/lib/types";
import { Unavailable } from "@/components/ui";
import { EvaluationResults } from "@/components/evaluation-results";
export const dynamic = "force-dynamic";
export default async function EvaluationsPage() {
  let data: EvaluationRun | null = null;
  try {
    data = await serverApi<EvaluationRun | null>("/evaluations");
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 404))
      return <Unavailable />;
  }
  return <EvaluationResults initial={data} />;
}
