import { redirect } from "next/navigation";

export default function Home({
  searchParams,
}: {
  searchParams: { token?: string };
}) {
  if (searchParams.token) {
    redirect(`/api/portal/auth?token=${searchParams.token}`);
  }
  redirect("/expired");
}
