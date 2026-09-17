import "server-only";
import { ApiError } from "./api";
import { checkedFrontendConfig } from "./server-runtime";

export async function serverApi<T>(path: string): Promise<T> {
  const { apiOrigin } = await checkedFrontendConfig();
  let response: Response;
  try {
    response = await fetch(`${apiOrigin}/api${path}`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
  } catch {
    throw new ApiError("The API is temporarily unavailable.", 503);
  }
  if (!response.ok)
    throw new ApiError(`The API returned ${response.status}.`, response.status);
  return response.json() as Promise<T>;
}
