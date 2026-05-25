import { type Dispatch, type FormEvent, type SetStateAction, useMemo, useState } from "react";
import { CheckCircle2, Send, Truck } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { DispatchPlannerCard } from "../components/DispatchPlannerCard";
import { LoadingState } from "../components/LoadingState";
import { useAllDispatchLoads, useCreateDispatchLoad } from "../hooks/useDispatch";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import type { DispatchCostType } from "../types/api";
import type { DispatchFormValues } from "../types/forms";
import { getLoadTotals, getPOPackedQty } from "../utils/factoryMetrics";
import { buildDispatchPayload, todayISO } from "../utils/forms";
import { formatCurrency, formatDate, formatNumber } from "../utils/format";

const emptyForm: DispatchFormValues = {
  purchase_order_id: "",
  load_number: "",
  shipped_qty: "",
  vehicle_type: "",
  vehicle_identifier: "",
  expected_piece_capacity: "",
  actual_loaded_pieces: "",
  cbm_capacity: "",
  cbm_used: "",
  cost_type: "invoice_percent",
  invoice_value: "",
  dispatch_percent: "0",
  cbm_value: "",
  cbm_rate: "",
  manual_cost: "",
  vehicle_cost: "",
  shipped_at: todayISO(),
  transporter_name: "",
  destination: "",
  tracking_reference: "",
  linked_repair_qty: "",
  linked_alteration_qty: "",
  shortfall_reason: "",
};

export default function DispatchPage() {
  const purchaseOrdersQuery = usePurchaseOrders();
  const [values, setValues] = useState<DispatchFormValues>(emptyForm);
  const dispatchQueries = useAllDispatchLoads(purchaseOrdersQuery.data);
  const createDispatchMutation = useCreateDispatchLoad();

  const allLoads = useMemo(
    () => dispatchQueries.flatMap((query) => query.data ?? []),
    [dispatchQueries],
  );
  const selectedPO = purchaseOrdersQuery.data?.find((po) => po.id === values.purchase_order_id);
  const packedQty = selectedPO ? getPOPackedQty(selectedPO) : 0;
  const shippedForSelected = allLoads
    .filter((load) => load.purchase_order_id === values.purchase_order_id)
    .reduce((sum, load) => sum + load.shipped_qty, 0);
  const availableToShip = Math.max(packedQty - shippedForSelected, 0);
  const totals = getLoadTotals(allLoads);
  const poNumberById = new Map((purchaseOrdersQuery.data ?? []).map((po) => [po.id, po.po_number]));
  const orderedQtyById = new Map((purchaseOrdersQuery.data ?? []).map((po) => [po.id, po.order_quantity_pcs]));
  const estimatedCost = getEstimatedDispatchCost(values);
  const shippedQty = toNumber(values.shipped_qty);
  const quantityInvalid = shippedQty <= 0 || shippedQty > availableToShip;
  const orderedQtyForSelected = selectedPO?.order_quantity_pcs ?? 0;
  const projectedTotalShipped = shippedForSelected + shippedQty;
  const projectedShortfall = Math.max(orderedQtyForSelected - projectedTotalShipped, 0);
  const enteredExceptionTotal = toNumber(values.linked_repair_qty) + toNumber(values.linked_alteration_qty);
  const exceptionMismatch =
    projectedShortfall > 0 && enteredExceptionTotal > 0 && enteredExceptionTotal !== projectedShortfall;

  if (purchaseOrdersQuery.isLoading) {
    return <LoadingState label="Loading dispatch board" />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createDispatchMutation.mutate(buildDispatchPayload(values), {
      onSuccess: () => setValues((current) => ({ ...emptyForm, purchase_order_id: current.purchase_order_id, shipped_at: todayISO() })),
    });
  }

  return (
    <div className="space-y-6">
      <DispatchPlannerCard />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,520px)_1fr]">
        <section className="panel p-5">
        <div className="flex items-center gap-2">
          <Truck className="h-5 w-5 text-teal-700" aria-hidden="true" />
          <div>
            <h1 className="text-xl font-bold text-slate-950">Dispatch Load</h1>
            <p className="text-sm text-slate-500">Create partial shipments and track cost per piece.</p>
          </div>
        </div>

        <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <div className="grid grid-cols-3 gap-3">
            <Metric label="Packed" value={formatNumber(packedQty)} />
            <Metric label="Shipped" value={formatNumber(shippedForSelected)} />
            <Metric label="Available" value={formatNumber(availableToShip)} strong />
          </div>
        </div>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <label className="label" htmlFor="purchase_order_id">
              Purchase Order
            </label>
            <select
              id="purchase_order_id"
              className="field"
              value={values.purchase_order_id}
              onChange={(event) => setValues((current) => ({ ...current, purchase_order_id: event.target.value }))}
              required
            >
              <option value="">Select PO</option>
              {(purchaseOrdersQuery.data ?? []).map((po) => (
                <option key={po.id} value={po.id}>
                  {po.po_number}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="load_number" label="Load Number" values={values} setValues={setValues} required />
            <TextField id="shipped_at" label="Ship Date" values={values} setValues={setValues} type="date" required />
            <TextField id="shipped_qty" label="Shipped Qty" values={values} setValues={setValues} type="number" max={availableToShip || undefined} required />
            <TextField id="vehicle_type" label="Vehicle Type" values={values} setValues={setValues} />
            <TextField id="vehicle_identifier" label="Vehicle ID" values={values} setValues={setValues} />
            <TextField id="transporter_name" label="Transporter" values={values} setValues={setValues} />
            <TextField id="destination" label="Destination" values={values} setValues={setValues} />
            <TextField id="tracking_reference" label="Tracking Ref" values={values} setValues={setValues} />
          </div>

          <div className="space-y-3 rounded-md border border-slate-200 p-3">
            <div className="space-y-2">
              <label className="label" htmlFor="cost_type">
                Cost Type
              </label>
              <select
                id="cost_type"
                className="field"
                value={values.cost_type}
                onChange={(event) => setValues((current) => ({ ...current, cost_type: event.target.value as DispatchFormValues["cost_type"] }))}
              >
                <option value="invoice_percent">Invoice Percent</option>
                <option value="cbm">CBM</option>
                <option value="manual">Manual</option>
                <option value="vehicle_capacity">Vehicle Capacity</option>
              </select>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {values.cost_type === "invoice_percent" ? (
                <>
                  <TextField id="invoice_value" label="Invoice Value" values={values} setValues={setValues} type="number" required />
                  <TextField id="dispatch_percent" label="Dispatch %" values={values} setValues={setValues} type="number" required />
                </>
              ) : null}
              {values.cost_type === "cbm" ? (
                <>
                  <TextField id="cbm_value" label="CBM" values={values} setValues={setValues} type="number" required />
                  <TextField id="cbm_rate" label="CBM Rate" values={values} setValues={setValues} type="number" required />
                </>
              ) : null}
              {values.cost_type === "manual" ? (
                <TextField id="manual_cost" label="Manual Cost" values={values} setValues={setValues} type="number" required />
              ) : null}
              {values.cost_type === "vehicle_capacity" ? (
                <>
                  <TextField id="vehicle_cost" label="Vehicle Cost" values={values} setValues={setValues} type="number" required />
                  <TextField id="actual_loaded_pieces" label="Actual Loaded Pieces" values={values} setValues={setValues} type="number" required />
                </>
              ) : null}
            </div>
            <div className="rounded-md bg-slate-50 px-3 py-2 text-sm">
              <span className="text-slate-500">Estimated cost</span>
              <span className="ml-2 font-semibold text-slate-950">{formatCurrency(estimatedCost)}</span>
            </div>
          </div>

          {projectedShortfall > 0 ? (
            <div className="space-y-3 rounded-md border border-amber-200 bg-amber-50 p-3">
              <div className="text-sm">
                <p className="font-semibold text-amber-900">
                  Short-dispatch detected: {formatNumber(projectedTotalShipped)} of {formatNumber(orderedQtyForSelected)} pieces
                </p>
                <p className="text-xs text-amber-800">
                  Allocate the {formatNumber(projectedShortfall)} missing pieces below so the owner sees where they went.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <TextField id="linked_repair_qty" label="Pieces in Repair" values={values} setValues={setValues} type="number" />
                <TextField id="linked_alteration_qty" label="Pieces in Alteration" values={values} setValues={setValues} type="number" />
              </div>
              <TextField id="shortfall_reason" label="Shortfall Reason" values={values} setValues={setValues} />
              {exceptionMismatch ? (
                <p className="text-xs font-semibold text-amber-900">
                  Repair + Alteration = {formatNumber(enteredExceptionTotal)} but shortfall = {formatNumber(projectedShortfall)}. The remainder will be recorded as unaccounted.
                </p>
              ) : null}
            </div>
          ) : null}

          {createDispatchMutation.isError ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {getApiErrorMessage(createDispatchMutation.error)}
            </div>
          ) : null}
          {createDispatchMutation.isSuccess ? (
            <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Dispatch load saved.
            </div>
          ) : null}

          {values.purchase_order_id && quantityInvalid ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Shipped quantity must be greater than zero and no more than approved packing stock.
            </div>
          ) : null}

          <button type="submit" className="primary-button w-full" disabled={createDispatchMutation.isPending || quantityInvalid}>
            <Send className="h-4 w-4" aria-hidden="true" />
            {createDispatchMutation.isPending ? "Creating Load" : "Create Dispatch Load"}
          </button>
        </form>
      </section>

      <section className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="panel p-4">
            <p className="label">Total Shipped</p>
            <p className="mt-2 text-2xl font-bold text-slate-950">{formatNumber(totals.shippedQty)}</p>
          </div>
          <div className="panel p-4">
            <p className="label">Dispatch Cost</p>
            <p className="mt-2 text-2xl font-bold text-slate-950">{formatCurrency(totals.dispatchCost)}</p>
          </div>
        </div>

        <div className="panel overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">All Loads</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Load</th>
                  <th className="px-4 py-3">PO</th>
                  <th className="px-4 py-3">Shipped / Ordered</th>
                  <th className="px-4 py-3">Repair</th>
                  <th className="px-4 py-3">Alteration</th>
                  <th className="px-4 py-3">Shortfall</th>
                  <th className="px-4 py-3">Cost Type</th>
                  <th className="px-4 py-3">Cost</th>
                  <th className="px-4 py-3">Cost/Pc</th>
                  <th className="px-4 py-3">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {allLoads.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-slate-500">
                      No dispatch loads yet.
                    </td>
                  </tr>
                ) : (
                  allLoads.map((load) => {
                    const ordered = orderedQtyById.get(load.purchase_order_id) ?? null;
                    const shortfall = load.shortfall_qty ?? 0;
                    return (
                      <tr key={load.id}>
                        <td className="px-4 py-3 font-semibold text-slate-950">{load.load_number}</td>
                        <td className="px-4 py-3 text-slate-600">{poNumberById.get(load.purchase_order_id) ?? "-"}</td>
                        <td className="px-4 py-3 text-slate-600">
                          {formatNumber(load.shipped_qty)}
                          {ordered != null ? <span className="text-slate-400"> / {formatNumber(ordered)}</span> : null}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{formatNumber(load.linked_repair_qty ?? 0)}</td>
                        <td className="px-4 py-3 text-slate-600">{formatNumber(load.linked_alteration_qty ?? 0)}</td>
                        <td className="px-4 py-3">
                          {shortfall > 0 ? (
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800" title={load.shortfall_reason ?? undefined}>
                              {formatNumber(shortfall)}
                            </span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{costTypeLabel(load.cost_type)}</td>
                        <td className="px-4 py-3 text-slate-600">{formatCurrency(load.dispatch_cost)}</td>
                        <td className="px-4 py-3 text-slate-600">{formatCurrency(load.cost_per_piece)}</td>
                        <td className="px-4 py-3 text-slate-600">{formatDate(load.shipped_at)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
      </div>
    </div>
  );
}

type DispatchKey = keyof DispatchFormValues;

function TextField({
  id,
  label,
  values,
  setValues,
  type = "text",
  max,
  required,
}: {
  id: DispatchKey;
  label: string;
  values: DispatchFormValues;
  setValues: Dispatch<SetStateAction<DispatchFormValues>>;
  type?: string;
  max?: number;
  required?: boolean;
}) {
  return (
    <div className="space-y-2">
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="field"
        type={type}
        min={type === "number" ? "0" : undefined}
        max={max}
        value={values[id]}
        onChange={(event) => setValues((current) => ({ ...current, [id]: event.target.value }))}
        required={required}
      />
    </div>
  );
}

function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getEstimatedDispatchCost(values: DispatchFormValues): number {
  if (values.cost_type === "invoice_percent") {
    return (toNumber(values.invoice_value) * toNumber(values.dispatch_percent)) / 100;
  }
  if (values.cost_type === "cbm") {
    return toNumber(values.cbm_value) * toNumber(values.cbm_rate);
  }
  if (values.cost_type === "manual") {
    return toNumber(values.manual_cost);
  }
  const loaded = Math.max(toNumber(values.actual_loaded_pieces), 1);
  return toNumber(values.vehicle_cost) / loaded;
}

function costTypeLabel(costType: DispatchCostType): string {
  const labels: Record<DispatchCostType, string> = {
    invoice_percent: "Invoice %",
    cbm: "CBM",
    manual: "Manual",
    vehicle_capacity: "Vehicle Cap.",
  };
  return labels[costType];
}

function Metric({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={strong ? "mt-1 font-bold text-teal-800" : "mt-1 font-semibold text-slate-950"}>{value}</p>
    </div>
  );
}
