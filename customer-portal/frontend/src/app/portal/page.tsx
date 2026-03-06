import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import PortalClient from "@/components/PortalClient";

const API = process.env.PORTAL_API_URL || "http://portal-backend:4010";

async function get(path: string, token: string) {
  const res = await fetch(`${API}/portal${path}`, {
    headers: { Cookie: `portal_token=${token}` },
    cache: "no-store",
  });
  if (res.status === 401) return null;
  return res.json();
}

export default async function PortalPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("portal_token")?.value;
  if (!token) redirect("/expired");

  const [me, progress, questions, plans] = await Promise.all([
    get("/me", token),
    get("/progress", token),
    get("/questions", token),
    get("/plans", token),
  ]);

  if (!me) redirect("/expired");

  return <PortalClient me={me} progress={progress} questions={questions} plans={plans ?? []} />;
}
