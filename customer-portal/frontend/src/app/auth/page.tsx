import { redirect } from "next/navigation";

export default async function AuthPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const params = await searchParams;
  if (params.token) {
    redirect(`/api/portal/auth?token=${params.token}`);
  }
  redirect("/expired");
}
