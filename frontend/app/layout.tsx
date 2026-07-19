import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FirstCheck | Venture Intelligence",
  description: "Evidence-first founder discovery and investment decision support."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
