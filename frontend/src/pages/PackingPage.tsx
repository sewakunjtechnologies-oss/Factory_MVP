import { type FormEvent, useState } from "react";
import { PackageCheck, RotateCcw } from "lucide-react";

import { api } from "../api/axios";
import { LoadingState } from "../components/LoadingState";
import { RiskBadge } from "../components/StatusBadge";
import { usePackingAnalysis } from "../hooks/usePacking";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import { formatNumber } from "../utils/format";

type Mode = "forward" | "reverse";

type PlanResponse = {
  mode: Mode;
  total_pieces: number;
  packers: number;
  target_days: number | null;
  per_packer_per_day: number;
  days_required: number;
  pieces_per_day_total: number;
  explanation: string;
};

export default function PackingPage() {
  const pos = usePurchaseOrders();

  // Planner state
  const [mode, setMode] = useState<Mode>("forward");
  const [totalPieces, setTotalPieces] = useState("");
  const [packers, setPackers] = useState("");
  const [targetDays, setTargetDays] = useState("");
  const [perPackerPerDay, setPerPackerPerDay] = useState("");
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planning, setPlanning] = useState(false);

  // PO analysis (existing)
  const [poId, setPoId] = useState("");
  const [avgPerPacker, setAvgPerPacker] = useState("100");
  const [actualPackers, setActualPackers] = useState("1");
  const analysis = usePackingAnalysis(poId || undefined, Number(avgPerPacker) || 1, Number(actualPackers) || 0);

  if (pos.isLoading) return <LoadingState label="Loading packing" />;

  async function handlePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPlanError(null);
    setPlanning(true);
    try {
      const payload: Record<string, unknown> = {
        mode,
        total_pieces: Number(totalPieces),
        packers: Number(packers),
      };
      if (mode === "forward") payload.target_days = Number(targetDays);
      else payload.per_packer_per_day = Number(perPackerPerDay);
      const response = await api.post<PlanResponse>("/packing/plan", payload);
      setPlan(response.data);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setPlanError(e.response?.data?.detail ?? e.message ?? "Could not calculate the plan.");
    } finally {
      setPlanning(false);
    }
  }

  function resetPlan() {
    setTotalPieces("");
    setPackers("");
    setTargetDays("");
    setPerPackerPerDay("");
    setPlan(null);
    setPlanError(null);
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="flex items-center gap-2">
          <PackageCheck className="h-5 w-5 text-teal-700" aria-hidden="true" />
          <div>
            <h1 className="text-xl font-bold text-slate-950">Packing Planner</h1>
            <p className="text-sm text-slate-500">
              Tell me what you have — I'll tell you what you need. Pack faster or with fewer people; pick what to plan.
            </p>
          </div>
        </div>

        <div className="mt-5 inline-flex rounded-md border border-slate-200 bg-slate-50 p-1 text-sm">
          <button
            type="button"
            className={`rounded px-3 py-1.5 font-semibold ${mode === "forward" ? "bg-white text-teal-800 shadow-sm" : "text-slate-600"}`}
            onClick={() => setMode("forward")}
          >
            Find per-day target
          </button>
          <button
            type="button"
            className={`rounded px-3 py-1.5 font-semibold ${mode === "reverse" ? "bg-white text-teal-800 shadow-sm" : "text-slate-600"}`}
            onClick={() => setMode("reverse")}
          >
            Find days needed
          </button>
        </div>

        <form className="mt-5 grid gap-4 sm:grid-cols-3" onSubmit={handlePlan}>
          <Field id="pp-total" label="Total pieces to pack" value={totalPieces} onChange={setTotalPieces} placeholder="e.g. 4000" />
          <Field id="pp-packers" label="Number of packers" value={packers} onChange={setPackers} placeholder="e.g. 4" />
          {mode === "forward" ? (
            <Field id="pp-days" label="Days to finish in" value={targetDays} onChange={setTargetDays} placeholder="e.g. 5" />
          ) : (
            <Field id="pp-rate" label="Pieces per packer per day" value={perPackerPerDay} onChange={setPerPackerPerDay} placeholder="e.g. 200" />
          )}
          <div className="sm:col-span-3 flex flex-wrap gap-2">
            <button type="submit" className="primary-button" disabled={planning}>
              {planning ? "Calculating…" : "Calculate"}
            </button>
            <button type="button" className="secondary-button" onClick={resetPlan}>
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Reset
            </button>
          </div>
        </form>

        {planError ? (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{planError}</div>
        ) : null}

        {plan ? (
          <div className="mt-5 rounded-lg border border-teal-200 bg-teal-50 p-4 space-y-3">
            <p className="text-sm text-slate-700">{plan.explanation}</p>
            <div className="grid gap-3 sm:grid-cols-4">
              <Stat label="Per packer / day" value={`${formatNumber(plan.per_packer_per_day)} pcs`} highlight />
              <Stat label="Team / day" value={`${formatNumber(plan.pieces_per_day_total)} pcs`} />
              <Stat label="Days required" value={`${formatNumber(plan.days_required)} ${plan.days_required === 1 ? "day" : "days"}`} highlight />
              <Stat label="Total to pack" value={`${formatNumber(plan.total_pieces)} pcs`} />
            </div>
          </div>
        ) : null}
      </section>

      <section className="panel p-5">
        <h2 className="text-base font-bold text-slate-950">Live PO packing risk</h2>
        <p className="text-sm text-slate-500">Compare a specific PO's remaining packing work against your packer team's actual capacity.</p>

        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <label className="label" htmlFor="po-select">Purchase order</label>
            <select id="po-select" className="field" value={poId} onChange={(e) => setPoId(e.target.value)}>
              <option value="">Select a PO</option>
              {(pos.data ?? []).map((po) => <option key={po.id} value={po.id}>{po.po_number}</option>)}
            </select>
          </div>
          <Field id="avg-per-packer" label="Average pieces / packer / day" value={avgPerPacker} onChange={setAvgPerPacker} />
          <Field id="actual-packers" label="Packers assigned" value={actualPackers} onChange={setActualPackers} />
        </div>

        {analysis.data ? (
          <div className="mt-5 space-y-4">
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Per-packer daily target for this PO</p>
              <p className="mt-1 text-3xl font-bold text-teal-800">
                {formatNumber(analysis.data.pieces_per_packer_per_day)}
                <span className="ml-2 text-base font-medium text-slate-600">pieces / packer / day</span>
              </p>
              <p className="mt-2 text-sm text-slate-600">
                {formatNumber(analysis.data.remaining_qty)} pieces remaining · {formatNumber(analysis.data.days_left)} days left · {formatNumber(analysis.data.actual_packers)} packer{analysis.data.actual_packers === 1 ? "" : "s"} assigned
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <Metric label="Remaining" value={formatNumber(analysis.data.remaining_qty)} />
              <Metric label="Days left" value={formatNumber(analysis.data.days_left)} />
              <Metric label="Daily team target" value={formatNumber(analysis.data.daily_target)} />
              <Metric label="Packers needed" value={formatNumber(analysis.data.required_packers)} strong />
              <div className="panel p-4">
                <p className="label">Risk</p>
                <div className="mt-3"><RiskBadge risk={analysis.data.packing_risk} /></div>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function Field({ id, label, value, onChange, placeholder }: { id: string; label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div className="space-y-2">
      <label className="label" htmlFor={id}>{label}</label>
      <input
        id={id}
        className="field"
        type="number"
        min="0"
        step="1"
        inputMode="numeric"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-0.5 truncate text-sm font-semibold tabular-nums ${highlight ? "text-teal-800" : "text-slate-950"}`}>{value}</p>
    </div>
  );
}

function Metric({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="panel p-4">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-lg tabular-nums ${strong ? "font-bold text-teal-800" : "font-semibold text-slate-950"}`}>{value}</p>
    </div>
  );
}
