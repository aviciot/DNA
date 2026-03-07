import { redirect } from "next/navigation";

export default function AuthPage({
  searchParams,
}: {
  searchParams: { token?: string };
}) {
  if (searchParams.token) {
    redirect(`/api/portal/auth?token=${searchParams.token}`);
  }
  redirect("/expired");
}
