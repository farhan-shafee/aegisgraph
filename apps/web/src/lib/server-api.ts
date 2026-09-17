import "server-only";
import { ApiError } from "./api";

export async function serverApi<T>(path: string): Promise<T> {
  const response = await fetch(
    `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8000"}/api${path}`,
    { cache: "no-store", signal: AbortSignal.timeout(10000) },
  );
  if (!response.ok)
    throw new ApiError(`The API returned ${response.status}.`, response.status);
  return response.json() as Promise<T>;
}
