import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

export async function POST(req: NextRequest, { params }: { params: { documentId: string } }) {
  const cookieStore = await cookies();
  const token = cookieStore.get("portal_token")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const formData = await req.formData();
  const res = await fetch(`${API}/portal/iso360/upload/${params.documentId}`, {
    method: "POST",
    headers: { Cookie: `portal_token=${token}` },
    body: formData,
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
