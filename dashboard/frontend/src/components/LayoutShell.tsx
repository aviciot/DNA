"use client";

import { usePathname } from "next/navigation";
import AppShell from "@/components/AppShell";

const PUBLIC_PATHS = ["/login"];

export default function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (PUBLIC_PATHS.includes(pathname)) return <>{children}</>;
  return <AppShell>{children}</AppShell>;
}
