"use client";

import { useState } from "react";
import { useLanguage } from "@/app/language/LanguageProvider";
import { assessHeaders } from "@/app/language/rtl_handler";
import { API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function apiPath(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

export function CaseForm() {
  const { locale, t } = useLanguage();
  const [query, setQuery] = useState("Do I have a claim for unfair dismissal?");
  const [edt, setEdt] = useState("2025-10-01");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(apiPath("/assess"), {
        method: "POST",
        credentials: "include",
        headers: assessHeaders(locale),
        body: JSON.stringify({
          query,
          language: locale,
          use_model: false,
          jurisdiction: "EW",
          facts: {
            edt,
            service_start_date: "2019-01-01",
            reason_for_dismissal: "conduct",
            was_procedure_followed: false,
            weekly_pay: 700,
            language: locale,
          },
        }),
      });
      if (!res.ok) throw new Error(`Assessment failed (${res.status})`);
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="case-query">{t("form.query", "Your question")}</Label>
        <Input
          id="case-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          dir={locale === "ar" ? "rtl" : "ltr"}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="case-edt">{t("form.edt", "Dismissal date (YYYY-MM-DD)")}</Label>
        <Input id="case-edt" type="date" value={edt} onChange={(e) => setEdt(e.target.value)} />
      </div>
      <Button type="submit" disabled={loading}>
        {loading ? t("form.loading", "Assessing…") : t("form.submit", "Run assessment")}
      </Button>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      {result ? <ResultView payload={result} /> : null}
    </form>
  );
}
import { ResultView } from "@/components/ResultView";
