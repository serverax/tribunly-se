"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function IntakePage() {
  const router = useRouter();
  const [dismissalDate, setDismissalDate] = useState("");
  const [reason, setReason] = useState("");
  const [tenure, setTenure] = useState("");

  function onContinue() {
    const facts = {
      effective_date_of_termination: dismissalDate,
      dismissal_reason: reason,
      months_employed: tenure ? Number(tenure) : undefined,
    };
    sessionStorage.setItem("lawapp_intake_facts", JSON.stringify(facts));
    router.push("/diagnosis");
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Case intake</h1>
      <p className="text-muted-foreground">
        Plain-English facts for unfair dismissal. Saved locally until you sign in
        to persist a case.
      </p>
      <Card>
        <CardHeader>
          <CardTitle>Your situation</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:max-w-md">
          <div className="space-y-2">
            <Label htmlFor="edt">When were you dismissed?</Label>
            <Input
              id="edt"
              type="date"
              value={dismissalDate}
              onChange={(e) => setDismissalDate(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="reason">What reason were you given?</Label>
            <Input
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. redundancy, conduct"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tenure">Months employed (approx)</Label>
            <Input
              id="tenure"
              type="number"
              value={tenure}
              onChange={(e) => setTenure(e.target.value)}
            />
          </div>
          <Button onClick={onContinue} disabled={!dismissalDate}>
            Continue to diagnosis
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
