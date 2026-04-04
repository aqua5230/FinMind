import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinMind",
  description: "FinMind stock chart frontend.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant">
      <body className="bg-[#f0ebe3] antialiased">{children}</body>
    </html>
  );
}
