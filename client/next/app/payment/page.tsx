"use client";

import { useState } from "react";
import { createPaymentSession } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";

export default function PaymentPage() {
  const [caseId, setCaseId] = useState("");
  const [session, setSession] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onPay() {
    setError(null);
    try {
      const res = await createPaymentSession(caseId);
      setSession(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Payment failed");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Payment</h1>
      <p className="text-muted-foreground">
        Stripe checkout via /api/workflow/payment/create. Test mode in local
        docker override.
      </p>
      <div className="max-w-md space-y-3">
        <Label htmlFor="pay-case">Case ID</Label>
        <Input
          id="pay-case"
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
        />
        <Button onClick={onPay} disabled={!caseId}>
          Create checkout session
        </Button>
      </div>
      {error && <Alert variant="destructive">{error}</Alert>}
      {session && (
        <pre className="overflow-auto rounded border border-border bg-card p-4 text-xs">
          {JSON.stringify(session, null, 2)}
        </pre>
      )}
    </div>
  );
}
