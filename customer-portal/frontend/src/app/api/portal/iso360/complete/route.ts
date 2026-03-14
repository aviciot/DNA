import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("portal_token")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const body = await req.json();
  const res = await fetch(`${API}/portal/iso360/complete`, {
    method: "POST",
    headers: { Cookie: `portal_token=${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
