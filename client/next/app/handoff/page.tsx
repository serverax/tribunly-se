"use client";

import { useState } from "react";
import { submitHandoffLead } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";

export default function HandoffPage() {
  const [email, setEmail] = useState("");
  const [summary, setSummary] = useState("");
  const [ok, setOk] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await submitHandoffLead({
        contact_email: email,
        case_summary: summary,
        referral_type: "solicitor",
      });
      setOk(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Handoff failed");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Solicitor handoff</h1>
      <p className="text-muted-foreground">
        Free referral capture when a case is beyond self-help. Partner integration
        deferred.
      </p>
      <form onSubmit={onSubmit} className="max-w-md space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="summary">Brief summary</Label>
          <Input
            id="summary"
            required
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
        </div>
        <Button type="submit">Submit referral</Button>
      </form>
      {ok && <Alert>Referral captured. A partner solicitor may contact you.</Alert>}
      {error && <Alert variant="destructive">{error}</Alert>}
    </div>
  );
}
