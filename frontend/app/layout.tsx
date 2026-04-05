/**
 * OmniRAG Next.js Shell — root layout
 *
 * Structure: Sidebar (rail + panel) + Main (4 tabs) + Footer
 * Dark theme, responsive 3-tier (mobile/tablet/desktop)
 */
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OmniRAG",
  description: "Universal GraphRAG Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0d0d0d] text-[#e8e8e8] font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
