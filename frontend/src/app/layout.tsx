import type { Metadata } from "next";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v15-appRouter";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { TimerProvider } from "@/lib/contexts/TimerContext";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { FloatingTimer } from "@/components/practice/FloatingTimer";
import { APP_TITLE, APP_DESCRIPTION } from "@/lib/utils/constants";
import "./globals.css";

export const metadata: Metadata = {
  title: APP_TITLE,
  description: APP_DESCRIPTION,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pl">
      <head>
        {/* KaTeX CSS */}
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css"
          crossOrigin="anonymous"
        />
      </head>
      <body className="min-h-screen flex flex-col">
        <AppRouterCacheProvider>
          <ThemeProvider>
            <TimerProvider>
              <Header />
              <main className="flex-1 py-8">
                <div className="max-w-[1200px] mx-auto px-6">
                  {children}
                </div>
              </main>
              <Footer />
              <FloatingTimer />
            </TimerProvider>
          </ThemeProvider>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
