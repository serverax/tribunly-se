import { Alert } from "@/components/ui/alert";

export default function AdminCompliancePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Compliance status</h1>
      <Alert>
        Deferred: proxy GET /admin/compliance-status from monolith or admin
        service.
      </Alert>
    </div>
  );
}
