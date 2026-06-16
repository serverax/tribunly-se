import { Alert } from "@/components/ui/alert";

export default function AdminReviewPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Review queue</h1>
      <Alert>
        Deferred: connect to lawapp-admin-service at port 8007 with reviewer SSO.
      </Alert>
    </div>
  );
}
