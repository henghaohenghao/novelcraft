import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import Navigation from "@/components/Navigation";

export const metadata: Metadata = {
  title: "NovelCraft - AI 小说工坊",
  description: "面向长篇网文、剧本杀、互动小说创作的多智能体协同平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="bg-claude-cream">
        <Providers>
          <Navigation />
          <main className="max-w-7xl mx-auto px-6 py-12">{children}</main>
        </Providers>
      </body>
    </html>
  );
}