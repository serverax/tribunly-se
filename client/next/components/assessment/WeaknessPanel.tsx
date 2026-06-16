import type { StructuredAssessment } from "@/types/assessment";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Props = {
  weaknesses?: string[];
  assessment?: StructuredAssessment | null;
};

export function WeaknessPanel({ weaknesses, assessment }: Props) {
  const items =
    weaknesses ||
    assessment?.key_weaknesses ||
    [];

  if (!items.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Honest weaknesses</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          No specific weaknesses flagged yet. Add more facts for a fuller picture.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Honest weaknesses</CardTitle>
        <p className="text-sm text-muted-foreground">
          Areas that may reduce claim strength or need evidence.
        </p>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-2 pl-5 text-sm">
          {items.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
