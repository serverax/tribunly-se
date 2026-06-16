"use client";

import Link from "next/link";
import { useCases } from "@/hooks/useCase";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const { data: cases, isLoading, error } = useCases();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Button asChild variant="outline">
          <Link href="/intake">New intake</Link>
        </Button>
      </div>
      {isLoading && <p className="text-muted-foreground">Loading cases...</p>}
      {error && (
        <p className="text-destructive">
          {error instanceof Error ? error.message : "Failed to load cases"}
        </p>
      )}
      {!isLoading && !error && (!cases || cases.length === 0) && (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            No saved cases. Sign in via the backend auth flow, then create a
            case from intake.
          </CardContent>
        </Card>
      )}
      <ul className="grid gap-4 sm:grid-cols-2">
        {cases?.map((c) => (
          <li key={c.id}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  <Link href={`/case/${c.id}`} className="hover:text-primary">
                    {c.title || `Case ${c.id.slice(0, 8)}`}
                  </Link>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Status: {c.status || "draft"}
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
