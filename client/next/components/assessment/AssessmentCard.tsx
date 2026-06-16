import type { StructuredAssessment } from "@/types/assessment";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";

type Props = {
  assessment: StructuredAssessment | null;
  loading?: boolean;
  error?: string | null;
};

export function AssessmentCard({ assessment, loading, error }: Props) {
  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6 text-muted-foreground">
          Running governed assessment...
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return <Alert variant="destructive">{error}</Alert>;
  }

  if (!assessment) return null;

  const insufficient =
    assessment.insufficient_grounding || assessment.status === "insufficient_grounding";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Assessment</CardTitle>
        <p className="text-sm text-muted-foreground">
          {assessment.claim_type || "unfair dismissal"} · strength:{" "}
          {assessment.strength || "uncertain"}
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {insufficient && (
          <Alert variant="warning">
            Insufficient grounding. We cannot state a confident answer without
            better sources. Consider speaking to a solicitor.
          </Alert>
        )}
        {assessment.deadline?.limitation_date && (
          <p>
            <strong>Tribunal deadline:</strong>{" "}
            {assessment.deadline.limitation_date}
            {assessment.deadline_mismatch && (
              <span className="text-amber-300"> (client calc mismatch)</span>
            )}
          </p>
        )}
        {assessment.recommended_next_step && (
          <p>
            <strong>Next step:</strong> {assessment.recommended_next_step}
          </p>
        )}
        {assessment.citations && assessment.citations.length > 0 && (
          <div>
            <strong>Citations</strong>
            <ul className="mt-1 list-disc pl-5">
              {assessment.citations.map((c, i) => (
                <li key={i}>
                  {c.cite || c.rule_key}
                  {c.url ? (
                    <>
                      {" "}
                      <a href={c.url} target="_blank" rel="noreferrer">
                        source
                      </a>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Not legal advice. Information and assessment only.
        </p>
      </CardContent>
    </Card>
  );
}
