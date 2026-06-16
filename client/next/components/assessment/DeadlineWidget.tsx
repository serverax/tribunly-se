"use client";

import { useState } from "react";
import type { DeadlineCalcResponse } from "@/types/assessment";
import { useDeadlineWasmOrApi } from "@/hooks/useAssessment";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";

export function DeadlineWidget({ initialEdt }: { initialEdt?: string }) {
  const [edt, setEdt] = useState(initialEdt || "");
  const [ecA, setEcA] = useState("");
  const [ecB, setEcB] = useState("");
  const [result, setResult] = useState<
    (DeadlineCalcResponse & { computed_via?: string }) | null
  >(null);

  const mutation = useDeadlineWasmOrApi();

  async function onCalc() {
    const data = await mutation.mutateAsync({
      edt,
      ec_day_a: ecA || undefined,
      ec_day_b: ecB || undefined,
      claim_type: "unfair_dismissal",
    });
    setResult(data);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Deadline tracker</CardTitle>
        <p className="text-sm text-muted-foreground">
          Deterministic ET limitation (rules table). WASM when available, API
          otherwise.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="edt">Effective date of termination</Label>
            <Input
              id="edt"
              type="date"
              value={edt}
              onChange={(e) => setEdt(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ec-a">ACAS Day A (optional)</Label>
            <Input
              id="ec-a"
              type="date"
              value={ecA}
              onChange={(e) => setEcA(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ec-b">ACAS Day B (optional)</Label>
            <Input
              id="ec-b"
              type="date"
              value={ecB}
              onChange={(e) => setEcB(e.target.value)}
            />
          </div>
        </div>
        <Button onClick={onCalc} disabled={!edt || mutation.isPending}>
          {mutation.isPending ? "Calculating..." : "Calculate deadline"}
        </Button>
        {mutation.isError && (
          <Alert variant="destructive">
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Calculation failed"}
          </Alert>
        )}
        {result?.limitation_date && (
          <Alert>
            Limitation date: <strong>{result.limitation_date}</strong>
            {result.computed_via && (
              <span className="ml-2 text-xs text-muted-foreground">
                via {result.computed_via}
              </span>
            )}
            {result.authority && (
              <p className="mt-1 text-xs">{result.authority}</p>
            )}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
