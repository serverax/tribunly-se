import Link from "next/link";
import { API_BASE, fetchHealth } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CaseForm } from "@/components/CaseForm";

export default async function HomePage() {
  let health: { status?: string } = {};
  let healthError = "";

  try {
    health = await fetchHealth();
  } catch (e) {
    healthError = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">
          UK Employment Claim Co-Pilot
        </h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Honest assessment, deadline tracking, and document drafting for unfair
          dismissal. Grounded in cited UK sources. Not a law firm.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild>
            <Link href="/diagnosis">Free diagnosis</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/intake">Start intake</Link>
          </Button>
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Multi-native assessment (EN / AR)</CardTitle>
        </CardHeader>
        <CardContent>
          <CaseForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API connection</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>
            <code className="rounded bg-accent px-1">NEXT_PUBLIC_API_URL</code>:{" "}
            {API_BASE || "(same-origin rewrites)"}
          </p>
          {healthError ? (
            <p className="mt-2 text-destructive" role="alert">
              Backend unreachable: {healthError}
            </p>
          ) : (
            <p className="mt-2">
              Backend health:{" "}
              <span className="rounded bg-emerald-900/40 px-2 py-0.5 text-emerald-300">
                {health.status || "ok"}
              </span>
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
