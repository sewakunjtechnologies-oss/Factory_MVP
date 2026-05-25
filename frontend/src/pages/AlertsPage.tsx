import { Bell, Zap } from "lucide-react";

import { AlertPanel } from "../components/AlertPanel";
import { LoadingState } from "../components/LoadingState";
import { useAlerts, useGenerateAlerts } from "../hooks/useDashboard";

export default function AlertsPage() {
  const alerts = useAlerts(false);
  const generate = useGenerateAlerts();

  if (alerts.isLoading) {
    return <LoadingState label="Loading alerts" />;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <Bell className="h-5 w-5 text-teal-700" />
          <div>
            <h1 className="text-xl font-bold text-slate-950">Alerts</h1>
            <p className="text-sm text-slate-500">Real risks from shortage, delay, rejection, packing, and shipment pressure.</p>
          </div>
        </div>
        <button className="secondary-button" onClick={() => generate.mutate()} disabled={generate.isPending}><Zap className="h-4 w-4" />Generate Alerts</button>
      </div>
      <AlertPanel alerts={alerts.data ?? []} />
    </div>
  );
}
