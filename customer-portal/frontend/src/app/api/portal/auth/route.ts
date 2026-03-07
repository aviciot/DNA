import { NextRequest, NextResponse } from "next/server";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get("token");
  if (!token) return NextResponse.redirect(new URL("/expired", req.url));

  const res = await fetch(`${API}/portal/auth?token=${token}`, {
    redirect: "manual",
  });

  if (res.status === 307 || res.status === 302 || res.status === 301) {
    const setCookie = res.headers.get("set-cookie");
    // Return HTML that sets cookie + redirects — avoids Next.js stripping Set-Cookie on redirects
    const html = `<html><head><meta http-equiv="refresh" content="0;url=/portal"></head><body></body></html>`;
    const response = new NextResponse(html, {
      status: 200,
      headers: { "Content-Type": "text/html" },
    });
    if (setCookie) response.headers.set("set-cookie", setCookie);
    return response;
  }

  return NextResponse.redirect(new URL("/expired", req.url));
}
