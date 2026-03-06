import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DNA Compliance Portal",
  description: "Your ISO certification self-service portal",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
