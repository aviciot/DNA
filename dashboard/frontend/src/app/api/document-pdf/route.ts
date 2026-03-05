import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const docId = req.nextUrl.searchParams.get("docId");
  const lang = req.nextUrl.searchParams.get("lang") || "en";
  const auth = req.headers.get("authorization") || "";

  const backendUrl = process.env.INTERNAL_API_URL || "http://dna-backend:3010";
  const r = await fetch(
    `${backendUrl}/api/v1/document-design/preview/customer-document/${docId}/pdf?lang=${lang}`,
    { headers: { Authorization: auth } }
  );

  const buf = await r.arrayBuffer();
  return new NextResponse(buf, {
    status: r.status,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": r.headers.get("Content-Disposition") || "attachment",
    },
  });
}
