import { NextRequest, NextResponse } from "next/server";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get("token");
  if (!token) return NextResponse.redirect(new URL("/expired", req.url));

  const res = await fetch(`${API}/portal/auth?token=${token}`, { redirect: "manual" });

  // Forward the Set-Cookie header to the browser
  const setCookie = res.headers.get("set-cookie");
  const location = res.headers.get("location") || "/portal";

  const redirect = NextResponse.redirect(new URL("/portal", req.url));
  if (setCookie) redirect.headers.set("set-cookie", setCookie);
  return redirect;
}
