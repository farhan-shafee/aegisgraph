import { checkedFrontendConfig } from "@/lib/server-runtime";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const bodyLimit = 65536;

function failure(detail: string, status: number) {
  return Response.json(
    { detail },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

async function proxy(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  try {
    const { publicDemo, apiOrigin } = await checkedFrontendConfig();
    const { path } = await context.params;
    if (!path.length || path.some((part) => !/^[A-Za-z0-9_-]+$/.test(part)))
      return failure("API route not found.", 404);
    const pathname = `/${path.join("/")}`;
    const isRead = request.method === "GET" || request.method === "HEAD";
    if (
      publicDemo &&
      !isRead &&
      !(
        request.method === "POST" &&
        /^\/incidents\/[^/]+\/analysis$/.test(pathname)
      )
    )
      return failure(
        "The public demo is read-only. This operation is unavailable.",
        403,
      );
    const headers = new Headers();
    const origin = request.headers.get("origin");
    // Preserve the real browser origin. The API validates its exact allowlist.
    // Never synthesize a trusted Origin for an arbitrary caller.
    if (origin) headers.set("Origin", origin);
    if (publicDemo && !isRead && !origin)
      return failure("A permitted browser origin is required.", 403);
    let body: Uint8Array | undefined;
    if (!isRead && request.body) {
      if (!request.headers.get("content-type")?.startsWith("application/json"))
        return failure("Use application/json for this request.", 415);
      if (Number(request.headers.get("content-length")) > bodyLimit)
        return failure("Request body is too large.", 413);
      const reader = request.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      let expired = false;
      const timer = setTimeout(() => {
        expired = true;
        void reader.cancel();
      }, 10000);
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > bodyLimit) {
            await reader.cancel();
            return failure("Request body is too large.", 413);
          }
          chunks.push(value);
        }
      } finally {
        clearTimeout(timer);
      }
      if (expired) return failure("Request body timed out.", 408);
      body = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        body.set(chunk, offset);
        offset += chunk.length;
      }
      headers.set("Content-Type", "application/json");
    }
    const search = new URL(request.url).search;
    if (search.length > 4096)
      return failure("Request query is too large.", 414);
    const response = await fetch(`${apiOrigin}/api${pathname}${search}`, {
      method: request.method,
      headers,
      body: body as BodyInit | undefined,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(publicDemo ? 15000 : 90000),
    });
    if (response.status >= 500)
      return failure("The API is temporarily unavailable.", 503);
    if (!response.headers.get("content-type")?.includes("application/json"))
      return failure("The API could not complete this request.", 502);
    const responseHeaders = new Headers({
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    const retryAfter = response.headers.get("retry-after");
    if (retryAfter && /^\d{1,6}$/.test(retryAfter))
      responseHeaders.set("Retry-After", retryAfter);
    return new Response(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return failure("The demo service is temporarily unavailable.", 503);
  }
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PATCH,
  proxy as PUT,
  proxy as DELETE,
};
