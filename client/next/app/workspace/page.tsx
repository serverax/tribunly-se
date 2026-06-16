"use client";

import { useCases } from "@/hooks/useCase";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function WorkspacePage() {
  const { data: cases, isLoading } = useCases();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Workspace</h1>
      <p className="text-muted-foreground">
        Your saved matters and active work. Full matter schema migration is
        deferred; cases API is canonical today.
      </p>
      {isLoading ? (
        <p>Loading workspace...</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {cases?.map((c) => (
            <Card key={c.id}>
              <CardHeader>
                <CardTitle className="text-base">
                  <Link href={`/case/${c.id}`}>{c.title || c.id}</Link>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Updated: {c.updated_at || c.created_at || "unknown"}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
