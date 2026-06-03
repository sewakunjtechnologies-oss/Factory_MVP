import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, CheckCircle2, ClipboardList, Factory, PackageSearch, Truck, Zap } from "lucide-react";

import { AlertPanel } from "../components/AlertPanel";
import { LoadingState } from "../components/LoadingState";
import { StatusBadge } from "../components/StatusBadge";
import { StatCard } from "../components/StatCard";
import { useDashboard, useGenerateAlerts } from "../hooks/useDashboard";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import { getDashboardMetrics } from "../utils/factoryMetrics";
import { formatNumber } from "../utils/format";
import type { AlertRead, DashboardPORead, PurchaseOrderRead, ReminderRead } from "../types/api";

type DashboardFilter =
  | "all"
  | "active_pos"
  | "delayed_pos"
  | "shipment_risk"
  | "fabric_shortage"
  | "pending_dispatch"
  | "completed_today"
  | string;

const filterLabels: Record<string, string> = {
  all: "Purchase Orders",
  active_pos: "Active POs",
  delayed_pos: "Delayed POs",
  shipment_risk: "Shipment Risk",
  fabric_shortage: "Fabric Shortage",
  pending_dispatch: "Pending Dispatch",
  completed_today: "Completed Today",
};

const reminderTypesByCard: Record<string, string[]> = {
  fabric_not_ordered: ["fabric_not_ordered", "fabric_order_pending"],
  mill_delivery_overdue: ["mill_delivery_overdue"],
  fabric_verification_pending: ["fabric_verification_pending"],
  stitching_short: ["stitching_output_short"],
  dispatch_due: ["dispatch_due"],
  reminders_due: [],
};

const alertTypesByCard: Record<string, string[]> = {
  cutting_wastage_high: ["high_cutting_wastage"],
  packing_risk: ["packing_risk"],
};

export default function DashboardPage() {
  const dashboardQuery = useDashboard();
  const purchaseOrdersQuery = usePurchaseOrders();
  const generateAlertsMutation = useGenerateAlerts();
  const [selectedFilter, setSelectedFilter] = useState<DashboardFilter>("all");

  const dashboard = dashboardQuery.data;
  const dashboardPOs = useMemo(() => dashboard?.purchase_orders ?? [], [dashboard]);
  const alerts = useMemo(() => dashboard?.alerts ?? [], [dashboard]);
  const reminders = useMemo(() => dashboard?.reminders ?? [], [dashboard]);
  const purchaseOrders = useMemo(() => purchaseOrdersQuery.data ?? [], [purchaseOrdersQuery.data]);
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
  const selectedLabel = filterLabels[selectedFilter] ?? (dashboard?.action_cards ?? []).find((card) => card.type === selectedFilter)?.label ?? "Selected Card";
  const relatedAlerts = useMemo(() => filterAlertsForCard(alerts, selectedFilter), [alerts, selectedFilter]);
  const relatedReminders = useMemo(() => filterRemindersForCard(reminders, selectedFilter), [reminders, selectedFilter]);
  const visiblePOs = useMemo(
    () => filterPOsForCard(dashboardPOs, selectedFilter, relatedAlerts, relatedReminders),
    [dashboardPOs, selectedFilter, relatedAlerts, relatedReminders],
  );
  const purchaseOrderById = useMemo(
    () => new Map(purchaseOrders.map((po) => [po.id, po])),
    [purchaseOrders],
  );
  const visiblePOGroups = useMemo(
    () => groupDashboardPOsByMonth(visiblePOs, purchaseOrderById),
    [visiblePOs, purchaseOrderById],
  );

  function toggleFilter(filter: DashboardFilter) {
    setSelectedFilter((current) => (current === filter ? "all" : filter));
  }

  if (dashboardQuery.isLoading) {
    return <LoadingState label="Loading owner dashboard" />;
  }

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
        <StatCard label="Active POs" value={metrics.activePOs} icon={Factory} tone="blue" active={selectedFilter === "active_pos"} onClick={() => toggleFilter("active_pos")} />
        <StatCard label="Delayed POs" value={metrics.delayedPOs} icon={AlertCircle} tone={metrics.delayedPOs ? "red" : "green"} active={selectedFilter === "delayed_pos"} onClick={() => toggleFilter("delayed_pos")} />
        <StatCard label="Shipment Risk" value={metrics.shipmentRisk} icon={Truck} tone={metrics.shipmentRisk ? "red" : "green"} active={selectedFilter === "shipment_risk"} onClick={() => toggleFilter("shipment_risk")} />
        <StatCard label="Fabric Shortage" value={metrics.fabricShortage} icon={PackageSearch} tone={metrics.fabricShortage ? "yellow" : "green"} active={selectedFilter === "fabric_shortage"} onClick={() => toggleFilter("fabric_shortage")} />
        <StatCard label="Pending Dispatch" value={metrics.pendingDispatch} icon={ClipboardList} tone="yellow" active={selectedFilter === "pending_dispatch"} onClick={() => toggleFilter("pending_dispatch")} />
        <StatCard label="Completed Today" value={metrics.completedToday} icon={CheckCircle2} tone="green" active={selectedFilter === "completed_today"} onClick={() => toggleFilter("completed_today")} />
      </section>

      {(dashboard?.action_cards ?? []).length > 0 ? (
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Today's open items</h2>
          <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 xl:grid-cols-5">
            {(dashboard?.action_cards ?? []).map((card) => (
              <button
                key={card.type}
                type="button"
                className={`panel p-3 text-left transition hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-teal-500 ${selectedFilter === card.type ? "ring-2 ring-teal-600" : ""}`}
                onClick={() => toggleFilter(card.type)}
                aria-pressed={selectedFilter === card.type}
              >
                <p className="text-[11px] font-medium text-slate-500">{card.label}</p>
                <p className={`mt-1 text-xl font-bold tabular-nums ${card.count > 0 ? "text-red-700" : "text-slate-400"}`}>
                  {formatNumber(card.count)}
                </p>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <section className="panel overflow-hidden">
          <div className="flex flex-col gap-2 border-b border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-950">{selectedLabel}</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                {selectedFilter === "all" ? "Tap a PO category to open the full workflow detail." : `${formatNumber(visiblePOs.length)} matching PO${visiblePOs.length === 1 ? "" : "s"} shown from the selected card.`}
              </p>
            </div>
            {selectedFilter !== "all" ? (
              <button type="button" className="secondary-button h-9 self-start sm:self-auto" onClick={() => setSelectedFilter("all")}>
                Show All
              </button>
            ) : null}
          </div>
          {selectedFilter !== "all" && (relatedAlerts.length > 0 || relatedReminders.length > 0) ? (
            <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
              <div className="grid gap-3 md:grid-cols-2">
                {relatedAlerts.length > 0 ? (
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Related alerts</p>
                    <div className="mt-2 space-y-2">
                      {relatedAlerts.slice(0, 4).map((alert) => (
                        <RelatedItem key={alert.id} title={alert.title} body={alert.message} tag={alert.priority} />
                      ))}
                    </div>
                  </div>
                ) : null}
                {relatedReminders.length > 0 ? (
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Related reminders</p>
                    <div className="mt-2 space-y-2">
                      {relatedReminders.slice(0, 4).map((reminder) => (
                        <RelatedItem key={reminder.id} title={reminder.title} body={reminder.message} tag={`Due ${reminder.due_date}`} />
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
          <div className="space-y-5 p-4">
            {visiblePOs.length === 0 ? (
              <div className="rounded-md border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-500">
                No information found for {selectedLabel}.
              </div>
            ) : null}
            {visiblePOGroups.map((group) => (
              <section key={group.key} className="space-y-3">
                <div className="flex flex-col gap-1 border-l-4 border-teal-500 pl-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <h3 className="text-lg font-extrabold text-slate-950">{group.label}</h3>
                    <p className="text-xs text-slate-500">{group.helper}</p>
                  </div>
                  <span className="text-xs font-semibold text-slate-500">{formatNumber(group.rows.length)} PO{group.rows.length === 1 ? "" : "s"}</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {group.rows.map((po) => (
                    <Link
                      key={po.purchase_order_id}
                      to={`/po/${po.purchase_order_id}`}
                      className="block rounded-md border border-slate-200 bg-white p-4 shadow-sm transition hover:border-teal-300 hover:bg-teal-50/50 focus:outline-none focus:ring-2 focus:ring-teal-500"
                      aria-label={`Open ${po.product}`}
                    >
                      <p className="break-words text-base font-extrabold leading-snug text-slate-950">{po.product}</p>
                      <div className="mt-3 flex items-center justify-between gap-3">
                        <span className="font-mono text-xs font-semibold text-slate-500">{po.po_number}</span>
                        <StatusBadge value={po.status} />
                      </div>
                    </Link>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </section>
        <div className="space-y-4">
          <AlertPanel alerts={alerts} />
          <section className="panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-950">Due reminders</h2>
              {reminders.length > 0 ? (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                  {reminders.length}
                </span>
              ) : null}
            </div>
            <div className="divide-y divide-slate-100">
              {reminders.slice(0, 8).map((reminder) => (
                <div key={reminder.id} className="px-4 py-3 text-sm">
                  <p className="font-semibold text-slate-900">{reminder.title}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    <span className="font-mono">{reminder.reminder_type}</span> · Due {reminder.due_date}
                  </p>
                </div>
              ))}
              {reminders.length === 0 ? <div className="px-4 py-8 text-center text-sm text-slate-500">No due reminders.</div> : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

type MonthGroup<T> = {
  key: string;
  label: string;
  helper: string;
  sortValue: number;
  rows: T[];
};

function groupDashboardPOsByMonth(
  rows: DashboardPORead[],
  purchaseOrderById: Map<string, PurchaseOrderRead>,
): MonthGroup<DashboardPORead>[] {
  return groupByMonth(rows, (po) => purchaseOrderById.get(po.purchase_order_id)?.order_date ?? inferMonthDateFromPONumber(po.po_number));
}

function groupByMonth<T>(rows: T[], getDate: (row: T) => string | null | undefined): MonthGroup<T>[] {
  const groups = new Map<string, MonthGroup<T>>();
  rows.forEach((row) => {
    const dateValue = getDate(row);
    const parsed = parseDate(dateValue);
    const key = parsed ? `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}` : "unknown";
    const label = parsed ? `${monthName(parsed)} POs` : "Other POs";
    const helper = parsed ? monthHelper(parsed) : "POs without a recorded order month.";
    const sortValue = parsed ? parsed.getFullYear() * 12 + parsed.getMonth() : -1;
    const group = groups.get(key) ?? { key, label, helper, sortValue, rows: [] };
    group.rows.push(row);
    groups.set(key, group);
  });
  return Array.from(groups.values()).sort((a, b) => b.sortValue - a.sortValue);
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function monthName(date: Date): string {
  return new Intl.DateTimeFormat("en", { month: "long", year: "numeric" }).format(date);
}

function monthHelper(date: Date): string {
  const month = date.getMonth();
  if (month === 5) return "June POs from the updated PDF status sheet.";
  if (month === 4) return "May POs and completed previous work.";
  return "POs grouped by order month for easier review.";
}

function inferMonthDateFromPONumber(poNumber: string): string | null {
  const value = poNumber.toLowerCase();
  if (value.includes("june")) return "2026-06-01";
  if (value.includes("may")) return "2026-05-01";
  return null;
}

function filterPOsForCard(
  rows: DashboardPORead[],
  filter: DashboardFilter,
  alerts: AlertRead[],
  reminders: ReminderRead[],
): DashboardPORead[] {
  if (filter === "all") return rows;
  if (filter === "active_pos") return rows.filter((po) => !["completed", "cancelled"].includes(po.status));
  if (filter === "delayed_pos") {
    const delayedIds = idsFrom([...alerts.filter((alert) => ["stage_delay", "contractor_delay"].includes(String(alert.alert_type)))]);
    return rows.filter((po) => po.status === "delayed" || delayedIds.has(po.purchase_order_id));
  }
  if (filter === "shipment_risk") return rows.filter((po) => po.shipment_risk);
  if (filter === "fabric_shortage") return rows.filter((po) => po.fabric_shortage_m > 0);
  if (filter === "pending_dispatch") return rows.filter((po) => po.pending_qty > 0 && ["dispatch", "partially_dispatched"].includes(po.status));
  if (filter === "completed_today") return rows.filter((po) => po.completed_qty > 0);

  const relatedIds = new Set<string>();
  alerts.forEach((alert) => {
    if (alert.purchase_order_id) relatedIds.add(alert.purchase_order_id);
  });
  reminders.forEach((reminder) => {
    if (reminder.purchase_order_id) relatedIds.add(reminder.purchase_order_id);
  });
  return rows.filter((po) => relatedIds.has(po.purchase_order_id));
}

function filterAlertsForCard(alerts: AlertRead[], filter: DashboardFilter): AlertRead[] {
  if (filter === "all") return [];
  if (filter === "delayed_pos") return alerts.filter((alert) => ["stage_delay", "contractor_delay"].includes(String(alert.alert_type)));
  if (filter === "shipment_risk") return alerts.filter((alert) => String(alert.alert_type) === "shipment_risk");
  if (filter === "fabric_shortage") return alerts.filter((alert) => String(alert.alert_type) === "stock_shortage");
  const types = alertTypesByCard[filter] ?? [];
  return alerts.filter((alert) => types.includes(String(alert.alert_type)));
}

function filterRemindersForCard(reminders: ReminderRead[], filter: DashboardFilter): ReminderRead[] {
  if (filter === "all") return [];
  if (filter === "fabric_shortage") return reminders.filter((reminder) => ["fabric_order_pending", "fabric_not_ordered", "fabric_stock_short"].includes(reminder.reminder_type));
  if (filter === "pending_dispatch") return reminders.filter((reminder) => reminder.reminder_type === "dispatch_due");
  const types = reminderTypesByCard[filter];
  if (filter === "reminders_due") return reminders;
  if (!types) return [];
  return reminders.filter((reminder) => types.includes(reminder.reminder_type));
}

function idsFrom(alerts: AlertRead[]): Set<string> {
  return new Set(alerts.map((alert) => alert.purchase_order_id).filter((id): id is string => Boolean(id)));
}

function RelatedItem({ title, body, tag }: { title: string; body: string; tag: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold text-slate-900">{title}</p>
        <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-600">{tag}</span>
      </div>
      <p className="mt-1 text-slate-600">{body}</p>
    </div>
  );
}
