import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("portal_token")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const body = await req.json();
  const res = await fetch(`${API}/portal/task-help`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Cookie: `portal_token=${token}` },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  }

  // Pass SSE stream straight through
  return new NextResponse(res.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
