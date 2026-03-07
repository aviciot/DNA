import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ task_id: string }> }
) {
  const cookieStore = await cookies();
  const token = cookieStore.get("portal_token")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { task_id } = await params;
  const body = await req.formData();
  const res = await fetch(`${API}/portal/upload/${task_id}`, {
    method: "POST",
    headers: { Cookie: `portal_token=${token}` },
    body,
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
