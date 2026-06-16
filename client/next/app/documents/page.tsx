"use client";

import { useState } from "react";
import { generateDocuments } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";

export default function DocumentsPage() {
  const [caseId, setCaseId] = useState("");
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onGenerate() {
    setLoading(true);
    setError(null);
    try {
      const res = await generateDocuments(caseId, "particulars_of_claim");
      setOutput(JSON.stringify(res, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Documents</h1>
      <p className="text-muted-foreground">
        Paid document generation via governed workflow. Requires auth and
        entitlement.
      </p>
      <div className="max-w-md space-y-3">
        <Label htmlFor="case-id">Case ID</Label>
        <Input
          id="case-id"
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
          placeholder="UUID from dashboard"
        />
        <Button onClick={onGenerate} disabled={!caseId || loading}>
          {loading ? "Generating..." : "Generate particulars (paid)"}
        </Button>
      </div>
      {error && <Alert variant="destructive">{error}</Alert>}
      {output && (
        <pre className="overflow-auto rounded border border-border bg-card p-4 text-xs">
          {output}
        </pre>
      )}
    </div>
  );
}
