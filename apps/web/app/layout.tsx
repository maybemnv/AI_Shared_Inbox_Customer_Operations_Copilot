import type { Metadata } from "next";
import "./tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Shared Inbox Operations",
  description: "Fixture-first customer operations workbench",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
