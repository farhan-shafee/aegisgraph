// A route handler bypasses page layouts, so unknown paths cannot spend API budget.
export const dynamic = "force-dynamic";

function notFound(request: Request) {
  return new Response(request.method === "HEAD" ? null : "Not found.\n", {
    status: 404,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export { notFound as GET, notFound as HEAD };
