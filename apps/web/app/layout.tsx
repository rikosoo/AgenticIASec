import type { ReactNode } from "react";
import "./globals.css";

export const metadata = { title: "PromptShield" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
