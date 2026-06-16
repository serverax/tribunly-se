import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { SiteNav } from "@/components/site-nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "LawApp | UK Employment Claim Co-Pilot",
  description:
    "Information and assessment only. Not a law firm. Not legal advice.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-GB">
      <body>
        <Providers>
          <SiteNav />
          <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
          <footer className="mx-auto max-w-5xl px-4 pb-12 text-xs text-muted-foreground">
            LawApp provides information and document drafting only. Not a law
            firm. Not legal advice.
          </footer>
        </Providers>
      </body>
    </html>
  );
}
