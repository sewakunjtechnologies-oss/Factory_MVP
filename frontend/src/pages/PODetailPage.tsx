import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, FileText, Layers, Package, Pencil, Scissors, Shirt, Trash2, Truck } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { fetchQuotationPdfBlob } from "../api/quotations";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { POEditDialog } from "../components/POEditDialog";
import { ProgressBar } from "../components/ProgressBar";
import { StageProgressCard } from "../components/StageProgressCard";
import { StatusBadge } from "../components/StatusBadge";
import { useContractors } from "../hooks/useContractors";
import { useDispatchLoads } from "../hooks/useDispatch";
import { useCapacityForecast, useCuttingAnalysis, useDueReminders, useFabricIssues, useFabricMillOrders, useMillFollowupsDue } from "../hooks/useOperations";
import { usePackingAnalysis } from "../hooks/usePacking";
import { useAllocations, useQualityFailures, useStageProgressEntries } from "../hooks/useProduction";
import { useDeletePurchaseOrder, usePurchaseOrder } from "../hooks/usePurchaseOrders";
import { getContractorCompletionPercent, getPOCompletedQty, getPOPendingQty, productionStages } from "../utils/factoryMetrics";
import { formatCurrency, formatDate, formatMeters, formatNumber, stageShortName } from "../utils/format";

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const poQuery = usePurchaseOrder(id);
  const deletePO = useDeletePurchaseOrder();
  const [editOpen, setEditOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [quotationBusy, setQuotationBusy] = useState(false);
  const [quotationError, setQuotationError] = useState<string | null>(null);
  const allocationQuery = useAllocations(id);
  const contractorsQuery = useContractors();
  const dispatchQuery = useDispatchLoads(id);
  const millOrdersQuery = useFabricMillOrders(id);
  const millFollowupsQuery = useMillFollowupsDue();
  const fabricIssueQuery = useFabricIssues(id);
  const cuttingAnalysisQuery = useCuttingAnalysis(id);
  const remindersQuery = useDueReminders();
  const qualityFailureQuery = useQualityFailures(id);
  const progressEntriesQuery = useStageProgressEntries(id);
  const packingAnalysisQuery = usePackingAnalysis(id, 100, 1);
  const packingForecastQuery = useCapacityForecast(id ?? null, "packing");

  if (poQuery.isLoading) {
    return <LoadingState label="Loading PO details" />;
  }

  const po = poQuery.data;
  if (!po) {
    return <EmptyState icon={Package} title="PO not found" message="The selected purchase order could not be loaded." />;
  }

  const product = po.product;
  const fabricPlan = po.fabric_plan;
  const stages = po.stage_summaries.filter((stage) => productionStages.includes(stage.stage));
  const completedQty = getPOCompletedQty(po);
  const pendingQty = getPOPendingQty(po);
  const overallPercent = po.order_quantity_pcs > 0 ? Math.round((completedQty / po.order_quantity_pcs) * 100) : 0;
  const contractorNameById = new Map((contractorsQuery.data ?? []).map((contractor) => [contractor.id, contractor.name]));

  async function handleDelete() {
    if (!po) return;
    await deletePO.mutateAsync(po.id);
    navigate("/pos", { replace: true });
  }

  async function handleQuotationPdf() {
    if (!po) return;
    setQuotationBusy(true);
    setQuotationError(null);
    try {
      const blob = await fetchQuotationPdfBlob(po.po_number);
      const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setQuotationError(getApiErrorMessage(err));
    } finally {
      setQuotationBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <Link to="/dashboard" className="inline-flex items-center gap-2 text-sm font-semibold text-teal-700">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Dashboard
          </Link>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-950">{po.po_number}</h1>
            <StatusBadge value={po.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">Promise date: {formatDate(po.promise_delivery_date)}</p>
        </div>
        <div className="flex flex-wrap items-stretch gap-3">
          <div className="panel min-w-56 flex-1 p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold text-slate-700">Overall dispatch</span>
              <span className="font-bold text-slate-950">{overallPercent}%</span>
            </div>
            <div className="mt-3">
              <ProgressBar value={overallPercent} tone={pendingQty > 0 ? "yellow" : "green"} />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <button type="button" className="secondary-button" onClick={() => void handleQuotationPdf()} disabled={quotationBusy}>
              <FileText className="h-4 w-4" /> {quotationBusy ? "Preparing" : "Quotation PDF"}
            </button>
            <button type="button" className="secondary-button" onClick={() => setEditOpen(true)}>
              <Pencil className="h-4 w-4" /> Edit
            </button>
            <button
              type="button"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-red-300 bg-white px-4 text-sm font-semibold text-red-700 transition hover:border-red-400 hover:bg-red-50"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="h-4 w-4" /> Delete
            </button>
          </div>
        </div>
      </div>
      {quotationError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700">
          {quotationError}
        </div>
      ) : null}

      {/* Stock interlink card — what's already in inventory for this PO's fabric */}
      <section className="panel border-teal-200 bg-teal-50/50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-teal-700" aria-hidden="true" />
            <div>
              <h2 className="text-sm font-bold text-slate-950">Inventory link</h2>
              <p className="text-xs text-slate-500">
                Fabric: <span className="font-mono">{po.design_code_snapshot ?? "—"}</span>
                {po.product ? <> · Category <span className="font-mono">{po.product.product_name}</span></> : null}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Metric label="Ordered" value={formatNumber(po.order_quantity_pcs)} suffix="pcs" />
            <Metric label="Already in stock" value={formatNumber(po.pieces_in_stock_for_fabric)} suffix="pcs" tone="success" />
            <Metric label="Still to make" value={formatNumber(po.pieces_to_make)} suffix="pcs" tone={po.pieces_to_make > 0 ? "alert" : undefined} />
          </div>
        </div>
        {po.pieces_in_stock_for_fabric > 0 && po.pieces_in_stock_for_fabric >= po.order_quantity_pcs ? (
          <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800">
            ✓ Full PO can be filled from existing stock — no fabric to cut or stitch.
          </p>
        ) : po.pieces_in_stock_for_fabric > 0 ? (
          <p className="mt-3 rounded-md border border-teal-200 bg-white px-3 py-2 text-xs text-teal-900">
            Inventory page shows <span className="font-bold">{formatNumber(po.pieces_in_stock_for_fabric)} pcs</span> of this fabric in stock.
            Only <span className="font-bold">{formatNumber(po.pieces_to_make)} pcs</span> need to be made for this PO.
          </p>
        ) : null}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="panel p-4">
          <div className="flex items-center gap-2">
            <Shirt className="h-4 w-4 text-teal-700" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-slate-950">Product Info</h2>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <Detail label="Size" value={product?.size} />
            <Detail label="Design" value={product?.design} />
            <Detail label="Design Source" value={po.design_status ?? "-"} />
            <Detail label="Design Code" value={po.design_code_snapshot ?? "-"} />
            <Detail label="Color" value={product?.color} />
            <Detail label="Design Name" value={po.design_name_snapshot ?? "-"} />
            <Detail label="GSM" value={product?.gsm} />
            <Detail label="Fabric" value={product?.fabric_type} />
            <Detail label="Width" value={formatMeters(product?.width)} />
          </dl>
        </div>

        <div className="panel p-4">
          <div className="flex items-center gap-2">
            <Scissors className="h-4 w-4 text-teal-700" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-slate-950">Fabric Planning</h2>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <Detail label="Required" value={formatMeters(fabricPlan?.required_m)} />
            <Detail label="Wastage" value={formatMeters(fabricPlan?.wastage_m)} />
            <Detail label="Total Meters" value={formatMeters(fabricPlan?.total_required_m)} />
            <Detail label="Approx Rolls" value={fabricPlan?.rolls_required ? formatNumber(fabricPlan.rolls_required) : "-"} />
            <Detail label="Shortage" value={formatMeters(fabricPlan?.shortage_m)} danger={Number(fabricPlan?.shortage_m ?? 0) > 0} />
          </dl>
        </div>

        <div className="panel p-4">
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-teal-700" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-slate-950">Quantity</h2>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <Detail label="Order Qty" value={formatNumber(po.order_quantity_pcs)} />
            <Detail label="Completed" value={formatNumber(completedQty)} />
            <Detail label="Pending" value={formatNumber(pendingQty)} warning={pendingQty > 0} />
            <Detail label="Selling" value={formatCurrency(po.selling_price)} />
            <Detail label="Packing Risk" value={packingAnalysisQuery.data?.packing_risk ? "Risk" : "OK"} warning={packingAnalysisQuery.data?.packing_risk} />
          </dl>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="border-b border-slate-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-950">Daily Progress Ledger</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Stage</th><th className="px-4 py-3">Completed</th><th className="px-4 py-3">Approved</th><th className="px-4 py-3">Failed</th><th className="px-4 py-3">Moved</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(progressEntriesQuery.data ?? []).slice(0, 12).map((entry) => {
                const stage = po.stage_summaries.find((summary) => summary.id === entry.stage_summary_id);
                return <tr key={entry.id}><td className="px-4 py-3 text-slate-600">{formatDate(entry.entry_date)}</td><td className="px-4 py-3 font-semibold text-slate-950">{stage ? stageShortName(stage.stage) : "-"}</td><td className="px-4 py-3">{formatNumber(entry.completed_today)}</td><td className="px-4 py-3">{formatNumber(entry.approved_today)}</td><td className="px-4 py-3">{formatNumber(entry.rejected_today + entry.repair_today + entry.alter_today)}</td><td className="px-4 py-3">{formatNumber(entry.moved_to_next_stage_today)}</td></tr>;
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="panel overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Fabric Order Tracking</h2>
          </div>
          <div className="divide-y divide-slate-100">
            {(millOrdersQuery.data ?? []).map((order) => (
              <div key={order.id} className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-3">
                <p className="font-semibold text-slate-900">{order.mill_name}</p>
                <p className="text-slate-600">{formatMeters(order.ordered_meters)}</p>
                <p className={order.status === "delayed" ? "font-semibold text-red-700" : "text-slate-600"}>{order.status} · {formatDate(order.committed_delivery_date)}</p>
              </div>
            ))}
            {(millOrdersQuery.data ?? []).length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No mill order recorded.</div> : null}
          </div>
        </div>

        <div className="panel overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Mill Follow-up & Fabric Issue</h2>
          </div>
          <div className="space-y-4 px-4 py-3 text-sm">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Due Follow-ups</p>
              {(millFollowupsQuery.data ?? []).filter((item) => (millOrdersQuery.data ?? []).some((order) => order.id === item.mill_order_id)).slice(0, 5).map((item) => (
                <p key={item.id} className="mt-1 text-slate-700">{formatDate(item.next_followup_date ?? item.followup_date)} · {item.status}</p>
              ))}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Issued To Cutting</p>
              {(fabricIssueQuery.data ?? []).slice(0, 5).map((issue) => (
                <p key={issue.id} className="mt-1 text-slate-700">{formatDate(issue.issue_date)} · {formatMeters(issue.issued_meters)}</p>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <div className="panel p-4">
          <h2 className="text-sm font-semibold text-slate-950">Cutting Wastage</h2>
          {(cuttingAnalysisQuery.data ?? []).slice(0, 1).map((row) => (
            <dl key={row.id} className="mt-3 grid gap-2 text-sm">
              <Detail label="Planned Wastage" value={formatMeters(row.planned_wastage_m)} />
              <Detail label="Actual Wastage" value={formatMeters(row.actual_wastage_m)} />
              <Detail label="Difference" value={formatMeters(row.wastage_difference_m)} warning={Number(row.wastage_difference_m) > 0} />
            </dl>
          ))}
          {(cuttingAnalysisQuery.data ?? []).length === 0 ? <p className="mt-3 text-sm text-slate-500">No cutting analysis yet.</p> : null}
        </div>
        <div className="panel p-4">
          <h2 className="text-sm font-semibold text-slate-950">Capacity Forecast</h2>
          {packingForecastQuery.data ? (
            <dl className="mt-3 grid gap-2 text-sm">
              <Detail label="Stage" value={packingForecastQuery.data.stage} />
              <Detail label="Days Required" value={packingForecastQuery.data.days_required} />
              <Detail label="Forecast Completion" value={formatDate(packingForecastQuery.data.forecast_completion_date)} />
              <Detail label="Shipment Risk" value={packingForecastQuery.data.shipment_risk ? "At risk" : "On track"} warning={packingForecastQuery.data.shipment_risk} />
            </dl>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Capacity profile missing for this PO.</p>
          )}
        </div>
        <div className="panel p-4">
          <h2 className="text-sm font-semibold text-slate-950">Reminders & Responsibility</h2>
          <div className="mt-3 space-y-2 text-sm">
            {(remindersQuery.data ?? []).filter((item) => item.purchase_order_id === po.id).slice(0, 6).map((item) => (
              <div key={item.id} className="rounded border border-slate-200 bg-slate-50 px-2 py-1.5">
                <p className="font-semibold text-slate-900">{item.title}</p>
                <p className="text-xs text-slate-500">{item.reminder_type} · {formatDate(item.due_date)}</p>
              </div>
            ))}
            {(remindersQuery.data ?? []).filter((item) => item.purchase_order_id === po.id).length === 0 ? <p className="text-slate-500">No due reminders.</p> : null}
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-950">Stage Progress</h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {stages.map((stage) => (
            <StageProgressCard key={stage.id} stage={stage} />
          ))}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="panel overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Contractor Allocation</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Contractor</th>
                  <th className="px-4 py-3">Stage</th>
                  <th className="px-4 py-3">Issued</th>
                  <th className="px-4 py-3">Completed</th>
                  <th className="px-4 py-3">Delay</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(allocationQuery.data ?? []).map((allocation) => {
                  return (
                    <tr key={allocation.id}>
                      <td className="px-4 py-3 font-semibold text-slate-950">{contractorNameById.get(allocation.contractor_id) ?? "Contractor"}</td>
                      <td className="px-4 py-3 text-slate-600">{stageShortName(allocation.stage)}</td>
                      <td className="px-4 py-3 text-slate-600">{formatNumber(allocation.issued_qty)}</td>
                      <td className="px-4 py-3">
                        <div className="min-w-28">
                          <div className="mb-1 flex justify-between text-xs text-slate-500">
                            <span>{formatNumber(allocation.completed_qty)}</span>
                            <span>{getContractorCompletionPercent(allocation.issued_qty, allocation.completed_qty)}%</span>
                          </div>
                          <ProgressBar value={getContractorCompletionPercent(allocation.issued_qty, allocation.completed_qty)} tone={allocation.delay_days ? "red" : "green"} />
                        </div>
                      </td>
                      <td className={allocation.delay_days ? "px-4 py-3 font-semibold text-red-700" : "px-4 py-3 text-slate-600"}>
                        {allocation.delay_days} days
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel overflow-hidden">
          <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
            <Truck className="h-4 w-4 text-teal-700" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-slate-950">Dispatch Loads</h2>
          </div>
          <div className="divide-y divide-slate-100">
            {(dispatchQuery.data ?? []).length === 0 ? (
              <div className="px-4 py-8 text-sm text-slate-500">No dispatch loads yet.</div>
            ) : (
              (dispatchQuery.data ?? []).map((load) => (
                <div key={load.id} className="grid gap-2 px-4 py-3 text-sm sm:grid-cols-4">
                  <div>
                    <p className="font-semibold text-slate-950">{load.load_number}</p>
                    <p className="text-xs text-slate-500">{formatDate(load.shipped_at)}</p>
                  </div>
                  <Detail label="Shipped" value={formatNumber(load.shipped_qty)} />
                  <Detail label="Cost/Pc" value={formatCurrency(load.cost_per_piece)} />
                  <Detail label="Value" value={formatCurrency(load.invoice_value)} />
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-amber-700" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-slate-950">Failure Tracking</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Stage</th>
                <th className="px-4 py-3">Qty</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3">Resolution</th>
                <th className="px-4 py-3">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(qualityFailureQuery.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    No quality failures recorded.
                  </td>
                </tr>
              ) : (
                (qualityFailureQuery.data ?? []).map((failure) => {
                  const stage = po.stage_summaries.find((summary) => summary.id === failure.stage_summary_id);
                  return (
                    <tr key={failure.id}>
                      <td className="px-4 py-3 text-slate-600">{stage ? stageShortName(stage.stage) : "-"}</td>
                      <td className="px-4 py-3 font-semibold text-slate-950">{formatNumber(failure.failed_qty)}</td>
                      <td className="px-4 py-3 text-slate-600">{failureActionLabel(failure.action)}</td>
                      <td className="px-4 py-3 text-slate-600">{failure.reason}</td>
                      <td className="px-4 py-3 text-slate-600">{failure.resolution ?? "Open"}</td>
                      <td className="px-4 py-3 text-slate-600">{formatDate(failure.action_date)}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {editOpen ? (
        <POEditDialog
          po={po}
          onClose={() => setEditOpen(false)}
          onSaved={() => setEditOpen(false)}
        />
      ) : null}

      {confirmDelete ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" role="dialog" aria-modal="true">
          <div className="panel w-full max-w-md p-5">
            <h3 className="text-base font-bold text-slate-950">Delete PO {po.po_number}?</h3>
            <p className="mt-2 text-sm text-slate-600">
              This permanently removes the purchase order and every linked record (fabric plan, stage progress, dispatch loads,
              reminders). Inventory rows are <span className="font-semibold">not</span> affected.
            </p>
            {deletePO.isError ? (
              <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {(deletePO.error as Error)?.message ?? "Could not delete."}
              </div>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="secondary-button" onClick={() => setConfirmDelete(false)} disabled={deletePO.isPending}>
                Cancel
              </button>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-red-600 px-4 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
                onClick={() => void handleDelete()}
                disabled={deletePO.isPending}
              >
                {deletePO.isPending ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value, suffix, tone }: { label: string; value: string; suffix?: string; tone?: "alert" | "success" }) {
  const cls =
    tone === "alert" ? "text-red-700"
    : tone === "success" ? "text-emerald-700"
    : "text-slate-950";
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-0.5 text-lg font-bold tabular-nums ${cls}`}>
        {value}
        {suffix ? <span className="ml-1 text-xs font-normal text-slate-500">{suffix}</span> : null}
      </p>
    </div>
  );
}

function Detail({ label, value, danger, warning }: { label: string; value: string | number | null | undefined; danger?: boolean; warning?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={danger ? "font-semibold text-red-700" : warning ? "font-semibold text-amber-700" : "font-semibold text-slate-950"}>
        {value ?? "-"}
      </dd>
    </div>
  );
}

function failureActionLabel(action: string): string {
  const labels: Record<string, string> = {
    repair_in_factory: "Repair in factory",
    return_to_contractor: "Return to contractor",
    reject: "Reject",
  };
  return labels[action] ?? action;
}
