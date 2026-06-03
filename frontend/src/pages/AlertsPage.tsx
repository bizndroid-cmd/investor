import { CreateAlertForm } from "@/components/alerts/CreateAlertForm";
import { AlertList } from "@/components/alerts/AlertList";

export function AlertsPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Price Alerts</h2>
      <CreateAlertForm />
      <AlertList />
    </div>
  );
}
