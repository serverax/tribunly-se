"use client";

import { useParams } from "next/navigation";
import { useCase } from "@/hooks/useCase";
import { DeadlineWidget } from "@/components/assessment/DeadlineWidget";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CasePage() {
  const params = useParams();
  const caseId = typeof params.id === "string" ? params.id : "";
  const { data: lawCase, isLoading, error } = useCase(caseId);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Case hub</h1>
      {isLoading && <p className="text-muted-foreground">Loading...</p>}
      {error && (
        <p className="text-destructive">
          {error instanceof Error ? error.message : "Failed to load case"}
        </p>
      )}
      {lawCase && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{lawCase.title || "Untitled case"}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-2">
              <p>ID: {lawCase.id}</p>
              <p>Status: {lawCase.status || "draft"}</p>
              <p>Claim: {lawCase.claim_type || "unfair_dismissal"}</p>
            </CardContent>
          </Card>
          <DeadlineWidget
            initialEdt={String(lawCase.key_dates?.effective_date_of_termination || "")}
          />
        </>
      )}
    </div>
  );
}
