"use client";

import ChatWidget from "./ChatWidget";
import { useAuthStore } from "@/stores/authStore";

export default function ChatWidgetWrapper() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (!isAuthenticated) {
    return null;
  }

  return <ChatWidget />;
}
