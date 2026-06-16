import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminIndexPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Admin (stub)</h1>
      <p className="text-muted-foreground">
        Reviewer gate UI lives on lawapp-admin-service (:8007) with SSO/MFA
        deferred. These routes are placeholders for future proxy wiring.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              <Link href="/admin/review">Review queue</Link>
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Curated answer verification (stub)
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              <Link href="/admin/compliance">Compliance</Link>
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Monolith /admin/compliance-status proxy (stub)
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
