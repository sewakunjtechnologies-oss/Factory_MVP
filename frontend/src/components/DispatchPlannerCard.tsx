import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Boxes, Loader2, Sparkles, Truck } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import {
  fetchVehicles,
  planDispatch,
  type DispatchPlanResponse,
  type VehicleRead,
} from "../api/dispatchPlanner";
import { useProducts } from "../hooks/usePurchaseOrders";
import type { UUID } from "../types/api";
import { formatNumber } from "../utils/format";

const CATEGORY_PRODUCT_KIND = "category";

export function DispatchPlannerCard() {
  const productsQuery = useProducts();
  const vehiclesQuery = useQuery({
    queryKey: ["vehicles"],
    queryFn: () => fetchVehicles(false),
    staleTime: 60_000,
  });

  const categories = useMemo(
    () =>
      (productsQuery.data ?? [])
        .filter((p) => p.product_category === CATEGORY_PRODUCT_KIND)
        .map((p) => p.product_name)
        .sort(),
    [productsQuery.data],
  );

  const [vehicleId, setVehicleId] = useState<UUID | "">("");
  const [priority, setPriority] = useState<string[]>([]);
  const [plan, setPlan] = useState<DispatchPlanResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Default: pick the smallest vehicle and put all categories in alphabetical order.
  useEffect(() => {
    if (!vehicleId && (vehiclesQuery.data?.length ?? 0) > 0) {
      setVehicleId(vehiclesQuery.data![0].id);
    }
  }, [vehiclesQuery.data, vehicleId]);
  useEffect(() => {
    if (priority.length === 0 && categories.length > 0) {
      setPriority(categories);
    }
  }, [categories, priority.length]);

  const selectedVehicle: VehicleRead | undefined = vehiclesQuery.data?.find((v) => v.id === vehicleId);

  function move(index: number, delta: -1 | 1) {
    setPriority((prev) => {
      const next = [...prev];
      const j = index + delta;
      if (j < 0 || j >= next.length) return prev;
      [next[index], next[j]] = [next[j], next[index]];
      return next;
    });
  }

  async function onPlan(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!vehicleId || priority.length === 0) return;
    setBusy(true);
    setError(null);
    setPlan(null);
    try {
      const response = await planDispatch({ vehicle_id: vehicleId, category_priority: priority });
      setPlan(response);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel overflow-hidden">
      <header className="flex items-start gap-3 border-b border-slate-200 px-5 py-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-teal-50 text-teal-700">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h2 className="text-base font-bold text-slate-950">Truck load planner</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Pick a vehicle + category priority. We fit bales by CBM and weight, fill the highest-priority category first,
            then spill into the next.
          </p>
        </div>
      </header>

      <form className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]" onSubmit={onPlan}>
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="label" htmlFor="planner-vehicle">Vehicle</label>
            <select
              id="planner-vehicle"
              className="field"
              value={vehicleId}
              onChange={(e) => setVehicleId(e.target.value as UUID | "")}
              required
              disabled={vehiclesQuery.isLoading}
            >
              <option value="">Select vehicle</option>
              {(vehiclesQuery.data ?? []).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} · {v.cbm_capacity} m³ · {Number(v.max_weight_kg).toLocaleString()} kg
                </option>
              ))}
            </select>
            {selectedVehicle ? (
              <p className="text-[11px] text-slate-500">
                Capacity: <span className="font-semibold">{selectedVehicle.cbm_capacity} m³</span>,{" "}
                <span className="font-semibold">{Number(selectedVehicle.max_weight_kg).toLocaleString()} kg</span>
                {selectedVehicle.notes ? ` · ${selectedVehicle.notes}` : ""}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <label className="label">Category priority</label>
            <ul className="divide-y divide-slate-100 rounded-md border border-slate-200 bg-white">
              {priority.length === 0 ? (
                <li className="px-3 py-3 text-xs text-slate-500">Loading categories…</li>
              ) : (
                priority.map((cat, i) => (
                  <li key={cat} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                    <span className="flex items-center gap-2">
                      <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-600">
                        {i + 1}
                      </span>
                      <span className="font-semibold text-slate-900">{cat}</span>
                    </span>
                    <span className="flex gap-1">
                      <button type="button" className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">
                        <ArrowUp className="h-3 w-3" />
                      </button>
                      <button type="button" className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30" onClick={() => move(i, 1)} disabled={i === priority.length - 1} aria-label="Move down">
                        <ArrowDown className="h-3 w-3" />
                      </button>
                    </span>
                  </li>
                ))
              )}
            </ul>
            <p className="text-[11px] text-slate-500">Truck fills #1 first; only spills into #2 if room remains.</p>
          </div>

          <button type="submit" className="primary-button w-full" disabled={busy || !vehicleId || priority.length === 0}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Truck className="h-4 w-4" />}
            {busy ? "Planning…" : "Plan this truck"}
          </button>

          {error ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div> : null}
        </div>

        <div>
          {plan ? <PlanOutput plan={plan} /> : (
            <div className="flex h-full items-center justify-center rounded-md border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-500">
              Click "Plan this truck" to see how many bales fit and which ones spill to the next truck.
            </div>
          )}
        </div>
      </form>
    </section>
  );
}

function PlanOutput({ plan }: { plan: DispatchPlanResponse }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
        <Metric label="CBM used" value={`${Number(plan.used_cbm).toFixed(2)} / ${plan.cbm_capacity} m³`} pct={plan.fill_pct_cbm} />
        <Metric label="Weight used" value={`${Number(plan.used_weight_kg).toFixed(0)} / ${Number(plan.max_weight_kg).toFixed(0)} kg`} pct={plan.fill_pct_weight} />
        <Metric label="Bales" value={formatNumber(plan.total_bales)} />
        <Metric label="Pieces" value={formatNumber(plan.total_pieces)} />
      </div>

      <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
        <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600">
          <Boxes className="h-3.5 w-3.5" /> Load
        </div>
        {plan.items.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-slate-500">Nothing fits — bale spec might be missing on the fabrics.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Fabric</th>
                <th className="px-3 py-2 text-right">Bales</th>
                <th className="px-3 py-2 text-right">Pieces</th>
                <th className="px-3 py-2 text-right">m³</th>
                <th className="px-3 py-2 text-right">kg</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {plan.items.map((it, i) => (
                <tr key={i}>
                  <td className="whitespace-nowrap px-3 py-2 font-semibold text-slate-900">{it.category}</td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-slate-700">{it.fabric_code}</td>
                  <td className="num-cell px-3 py-2">{formatNumber(it.bales)}</td>
                  <td className="num-cell px-3 py-2">{formatNumber(it.pieces)}</td>
                  <td className="num-cell px-3 py-2">{Number(it.cbm).toFixed(3)}</td>
                  <td className="num-cell px-3 py-2">{Number(it.weight_kg).toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {plan.leftover.length > 0 ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <p className="font-semibold">Did not fit (next truck):</p>
          <ul className="mt-1 list-disc pl-5">
            {plan.leftover.map((lv, i) => (
              <li key={i}>
                <span className="font-mono">{lv.category} / {lv.fabric_code}</span> — {formatNumber(lv.available_pieces)} pcs · <span className="opacity-80">{lv.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value, pct }: { label: string; value: string; pct?: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-bold tabular-nums text-slate-950">{value}</p>
      {pct !== undefined ? (
        <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-slate-100">
          <div className="h-full bg-teal-500" style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
        </div>
      ) : null}
    </div>
  );
}
