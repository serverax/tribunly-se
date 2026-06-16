"use client";

type ResultViewProps = {
  payload: Record<string, unknown>;
};

/** Displays server-rendered native assessment fields (not client translation). */
export function ResultView({ payload }: ResultViewProps) {
  const rendered = (payload.rendered as Record<string, unknown>) || payload;
  const formatted = (rendered.formatted as Record<string, unknown>) || {};
  const summary = String(
    rendered.reasoning_summary ?? formatted["الملخص"] ?? payload.reasoning_summary ?? "",
  );
  const headline = String(rendered.headline ?? formatted["العنوان"] ?? "");
  const weaknesses =
    (rendered.key_weaknesses as string[]) ??
    (formatted["نقاط_الضعف"] as string[]) ??
    [];
  const locale = String(payload.locale ?? "en");
  const dir = String(payload.dir ?? payload.direction ?? (locale === "ar" ? "rtl" : "ltr"));

  return (
    <article className="rounded-lg border border-border bg-card p-4 text-sm" dir={dir as "ltr" | "rtl"}>
      <p className="text-xs text-muted-foreground">
        {locale.toUpperCase()} · {dir.toUpperCase()} · native server render
      </p>
      {headline ? <h3 className="mt-2 text-lg font-semibold">{headline}</h3> : null}
      <p className="mt-2 whitespace-pre-wrap">{summary}</p>
      {weaknesses.length ? (
        <ul className="mt-3 list-disc space-y-1 ps-5">
          {weaknesses.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}
