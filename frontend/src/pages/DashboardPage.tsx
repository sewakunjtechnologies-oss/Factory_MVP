import { Link } from "react-router-dom";
import { AlertCircle, CheckCircle2, ClipboardList, Factory, PackageSearch, Truck, Zap } from "lucide-react";

import { AlertPanel } from "../components/AlertPanel";
import { LoadingState } from "../components/LoadingState";
import { ProgressBar } from "../components/ProgressBar";
import { RiskBadge, StatusBadge } from "../components/StatusBadge";
import { StatCard } from "../components/StatCard";
import { useDashboard, useGenerateAlerts } from "../hooks/useDashboard";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import { getDashboardMetrics } from "../utils/factoryMetrics";
import { formatNumber, stageShortName } from "../utils/format";

export default function DashboardPage() {
  const dashboardQuery = useDashboard();
  const purchaseOrdersQuery = usePurchaseOrders();
  const generateAlertsMutation = useGenerateAlerts();

  if (dashboardQuery.isLoading) {
    return <LoadingState label="Loading owner dashboard" />;
  }

  const dashboard = dashboardQuery.data;
  const purchaseOrders = purchaseOrdersQuery.data ?? [];
  const metrics = dashboard
    ? {
        activePOs: dashboard.active_pos,
        delayedPOs: dashboard.delayed_pos,
        shipmentRisk: dashboard.shipment_risks,
        fabricShortage: dashboard.fabric_shortages,
        pendingDispatch: dashboard.pending_dispatch,
        completedToday: dashboard.completed_today,
      }
    : getDashboardMetrics([], [], purchaseOrders);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-950">Owner Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">The current production picture across POs, risks, and dispatch.</p>
        </div>
        <button type="button" className="secondary-button" onClick={() => generateAlertsMutation.mutate()} disabled={generateAlertsMutation.isPending}>
          <Zap className="h-4 w-4" aria-hidden="true" />
          Refresh Alerts
        </button>
      </div>

      <section className="grid gap-3 grid-cols-2 sm:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Active POs" value={metrics.activePOs} icon={Factory} tone="blue" />
        <StatCard label="Delayed POs" value={metrics.delayedPOs} icon={AlertCircle} tone={metrics.delayedPOs ? "red" : "green"} />
        <StatCard label="Shipment Risk" value={metrics.shipmentRisk} icon={Truck} tone={metrics.shipmentRisk ? "red" : "green"} />
        <StatCard label="Fabric Shortage" value={metrics.fabricShortage} icon={PackageSearch} tone={metrics.fabricShortage ? "yellow" : "green"} />
        <StatCard label="Pending Dispatch" value={metrics.pendingDispatch} icon={ClipboardList} tone="yellow" />
        <StatCard label="Completed Today" value={metrics.completedToday} icon={CheckCircle2} tone="green" />
      </section>

      {(dashboard?.action_cards ?? []).length > 0 ? (
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Today's open items</h2>
          <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 xl:grid-cols-5">
            {(dashboard?.action_cards ?? []).map((card) => (
              <div key={card.type} className="panel p-3">
                <p className="text-[11px] font-medium text-slate-500">{card.label}</p>
                <p className={`mt-1 text-xl font-bold tabular-nums ${card.count > 0 ? "text-red-700" : "text-slate-400"}`}>
                  {formatNumber(card.count)}
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <section className="panel overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Purchase Orders</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">PO Number</th>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Order Qty</th>
                  <th className="px-4 py-3">Completed</th>
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3">Pending</th>
                  <th className="px-4 py-3">Bottleneck</th>
                  <th className="px-4 py-3">Shipment</th>
                  <th className="px-4 py-3">Urgent Action</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {(dashboard?.purchase_orders ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-10 text-center text-sm text-slate-500">
                      No active purchase orders.
                    </td>
                  </tr>
                ) : null}
                {(dashboard?.purchase_orders ?? []).map((po) => (
                  <tr key={po.purchase_order_id} className="align-middle hover:bg-slate-50">
                    <td className="whitespace-nowrap px-4 py-3 font-semibold text-teal-800">
                      <Link to={`/po/${po.purchase_order_id}`} className="hover:underline">{po.po_number}</Link>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{po.product}</td>
                    <td className="num-cell px-4 py-3 text-slate-700">{formatNumber(po.order_quantity_pcs)}</td>
                    <td className="num-cell px-4 py-3 text-slate-700">{formatNumber(po.completed_qty)}</td>
                    <td className="min-w-32 px-4 py-3">
                      <ProgressBar
                        value={po.order_quantity_pcs > 0 ? Math.round((po.completed_qty / po.order_quantity_pcs) * 100) : 0}
                        tone={po.shipment_risk ? "red" : "green"}
                      />
                    </td>
                    <td className="num-cell px-4 py-3 font-semibold text-slate-950">{formatNumber(po.pending_qty)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                      {po.bottleneck_stage ? stageShortName(po.bottleneck_stage) : "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <RiskBadge risk={po.shipment_risk} />
                    </td>
                    <td className="px-4 py-3 text-slate-700">{po.next_urgent_action || "—"}</td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <StatusBadge value={po.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <div className="space-y-4">
          <AlertPanel alerts={dashboard?.alerts ?? []} />
          <section className="panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-950">Due reminders</h2>
              {(dashboard?.reminders ?? []).length > 0 ? (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                  {(dashboard?.reminders ?? []).length}
                </span>
              ) : null}
            </div>
            <div className="divide-y divide-slate-100">
              {(dashboard?.reminders ?? []).slice(0, 8).map((reminder) => (
                <div key={reminder.id} className="px-4 py-3 text-sm">
                  <p className="font-semibold text-slate-900">{reminder.title}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    <span className="font-mono">{reminder.reminder_type}</span> · Due {reminder.due_date}
                  </p>
                </div>
              ))}
              {(dashboard?.reminders ?? []).length === 0 ? <div className="px-4 py-8 text-center text-sm text-slate-500">No due reminders.</div> : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
