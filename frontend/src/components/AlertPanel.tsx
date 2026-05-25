import { AlertTriangle } from "lucide-react";

import type { AlertRead } from "../types/api";
import { AlertPriorityBadge } from "./StatusBadge";
import { titleCase } from "../utils/format";

export function AlertPanel({ alerts }: { alerts: AlertRead[] }) {
  const criticalAlerts = alerts.filter((alert) => ["critical", "high"].includes(alert.priority));

  return (
    <aside className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-600" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-slate-950">Critical Alerts</h2>
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
          {criticalAlerts.length}
        </span>
      </div>

      {criticalAlerts.length === 0 ? (
        <div className="px-4 py-8 text-sm text-slate-500">No critical alerts.</div>
      ) : (
        <div className="divide-y divide-slate-100">
          {criticalAlerts.slice(0, 8).map((alert) => (
            <div key={alert.id} className="px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-950">{alert.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{titleCase(alert.alert_type)}</p>
                </div>
                <AlertPriorityBadge priority={alert.priority} />
              </div>
              <p className="mt-2 text-sm leading-5 text-slate-600">{alert.message}</p>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
