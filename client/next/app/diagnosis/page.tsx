"use client";

import { useEffect, useState } from "react";
import { AssessmentCard } from "@/components/assessment/AssessmentCard";
import { WeaknessPanel } from "@/components/assessment/WeaknessPanel";
import { DeadlineWidget } from "@/components/assessment/DeadlineWidget";
import { useDiagnosis } from "@/hooks/useAssessment";
import { Button } from "@/components/ui/button";
import type { StructuredAssessment } from "@/types/assessment";

export default function DiagnosisPage() {
  const [facts, setFacts] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<StructuredAssessment | null>(null);
  const diagnosis = useDiagnosis();

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("lawapp_intake_facts");
      if (raw) setFacts(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  async function run() {
    const data = await diagnosis.mutateAsync({
      query: "unfair dismissal assessment",
      facts,
      jurisdiction: "EW",
    });
    setResult(data);
    sessionStorage.setItem("lawapp_assessment", JSON.stringify(data));
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Free diagnosis</h1>
      <p className="text-muted-foreground">
        Governed brain pipeline: rules first, retrieval, CitationGuard. Not legal
        advice.
      </p>
      <Button onClick={run} disabled={diagnosis.isPending}>
        {diagnosis.isPending ? "Assessing..." : "Run assessment"}
      </Button>
      <AssessmentCard
        assessment={result}
        loading={diagnosis.isPending}
        error={
          diagnosis.isError
            ? diagnosis.error instanceof Error
              ? diagnosis.error.message
              : "Assessment failed"
            : null
        }
      />
      <WeaknessPanel assessment={result} />
      <DeadlineWidget
        initialEdt={String(facts.effective_date_of_termination || "")}
      />
    </div>
  );
}
