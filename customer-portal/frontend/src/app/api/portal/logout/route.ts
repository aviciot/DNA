import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

export async function POST() {
  const token = cookies().get("portal_token")?.value;
  if (token) {
    await fetch(`${API}/portal/logout`, {
      method: "POST",
      headers: { Cookie: `portal_token=${token}` },
    });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.delete("portal_token");
  return res;
}
