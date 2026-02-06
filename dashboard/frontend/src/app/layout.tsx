import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ChatWidgetWrapper from "@/components/ChatWidgetWrapper";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "DNA - ISO Certification Dashboard",
  description: "Modern dashboard for managing ISO certification workflows",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
        <ChatWidgetWrapper />
      </body>
    </html>
  );
}
