import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

export async function GET(req: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("portal_token")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const planId = req.nextUrl.searchParams.get("plan_id") ?? "";
  const url = `${API}/portal/iso360${planId ? `?plan_id=${planId}` : ""}`;

  const res = await fetch(url, {
    headers: { Cookie: `portal_token=${token}` },
    cache: "no-store",
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
