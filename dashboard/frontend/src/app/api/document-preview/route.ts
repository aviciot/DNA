import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const docId = req.nextUrl.searchParams.get("docId");
  const lang = req.nextUrl.searchParams.get("lang") || "en";
  // Prefer Authorization header; fall back to ?token= query param (needed for iframe navigation)
  const tokenParam = req.nextUrl.searchParams.get("token");
  const auth = req.headers.get("authorization") || (tokenParam ? `Bearer ${tokenParam}` : "");

  const backendUrl = process.env.INTERNAL_API_URL || "http://dna-backend:3010";
  const fwdHeaders: Record<string, string> = {};
  // Server-side proxy: use internal service token (already trusted inside Docker network)
  const internalToken = process.env.CF_INTERNAL_SERVICE_TOKEN;
  if (internalToken) {
    fwdHeaders["X-Internal-Service-Token"] = internalToken;
  } else if (auth) {
    fwdHeaders["Authorization"] = auth;
  }

  const r = await fetch(
    `${backendUrl}/api/v1/document-design/preview/customer-document/${docId}?lang=${lang}`,
    { headers: fwdHeaders }
  );

  const html = await r.text();
  return new NextResponse(html, {
    status: r.status,
    headers: { "Content-Type": "text/html" },
  });
}
