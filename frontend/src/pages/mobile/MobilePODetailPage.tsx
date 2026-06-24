import { Bot, FileText, History, Pencil, X } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getApiErrorMessage } from "../../api/axios";
import { LoadingState } from "../../components/LoadingState";
import { useExecuteMobileTransition, useMobilePOs, useMobileTransitionPreview } from "../../hooks/useMobileWorkflow";
import type { UUID } from "../../types/api";
import { formatMeters, formatNumber } from "../../utils/format";

export default function MobilePODetailPage() {
  const { id } = useParams();
  const poId = id as UUID;
  const pos = useMobilePOs();
  const preview = useMobileTransitionPreview(poId);
  const execute = useExecuteMobileTransition(poId);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});

  const po = useMemo(() => (pos.data ?? []).find((row) => row.id === poId), [pos.data, poId]);

  if (pos.isLoading || preview.isLoading) return <LoadingState />;
  if (!po) return <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">PO not found.</div>;

  const canMove = preview.data?.can_execute ?? false;

  async function handleConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payloadValues: Record<string, unknown> = {};
    for (const field of preview.data?.required_fields ?? []) {
      const raw = values[field.name] ?? field.default ?? "";
      payloadValues[field.name] = field.type === "number" ? Number(raw || 0) : raw;
    }
    await execute.mutateAsync({ values: payloadValues, confirm: true });
    setSheetOpen(false);
    setValues({});
  }

  return (
    <div className="space-y-4">
      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="font-mono text-xs font-bold uppercase tracking-wide text-teal-700">{po.po_number}</p>
        <h1 className="mt-1 text-xl font-black text-slate-950">{po.fabric_code || po.category_name}</h1>
        <p className="mt-1 text-sm text-slate-500">{formatNumber(po.quantity)} pcs · delivery {po.delivery_label}</p>
        <div className="mt-4 rounded-2xl bg-slate-100 p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Current stage</p>
          <p className="mt-1 text-lg font-black text-slate-950">{po.current_stage.replaceAll("_", " ")}</p>
        </div>
        {po.warning ? <p className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm font-semibold text-amber-800">{po.warning}</p> : null}
      </section>

      <section className="grid grid-cols-3 gap-2">
        <Fact label="Required" value={po.required_fabric_m ? `${formatMeters(Number(po.required_fabric_m))} m` : "-"} />
        <Fact label="Available" value={po.available_fabric_m ? `${formatMeters(Number(po.available_fabric_m))} m` : "-"} />
        <Fact label="Short" value={po.shortage_m ? `${formatMeters(Number(po.shortage_m))} m` : "0 m"} />
      </section>

      <button
        type="button"
        className="primary-button min-h-16 w-full rounded-2xl text-base"
        disabled={!canMove}
        onClick={() => setSheetOpen(true)}
      >
        {preview.data?.action_label ?? po.next_action_label}
      </button>

      <section className="grid grid-cols-2 gap-2">
        <SmallAction icon={Pencil} label="Edit PO" />
        <SmallAction icon={History} label="View History" />
        <Link to="/mobile/assistant" className="flex min-h-14 items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700">
          <Bot className="h-4 w-4" /> Ask AI
        </Link>
        <SmallAction icon={FileText} label="Generate PDF" />
      </section>

      {execute.isError ? <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{getApiErrorMessage(execute.error)}</div> : null}

      {sheetOpen && preview.data ? (
        <div className="fixed inset-0 z-50 flex items-end bg-slate-950/40">
          <form className="max-h-[88dvh] w-full overflow-y-auto rounded-t-3xl bg-white p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]" onSubmit={handleConfirm}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Current: {preview.data.current_stage.replaceAll("_", " ")}</p>
                <h2 className="mt-1 text-xl font-black text-slate-950">{preview.data.action_label}</h2>
                <p className="mt-1 text-sm text-slate-500">Next: {preview.data.next_stage.replaceAll("_", " ")}</p>
              </div>
              <button type="button" className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-600" onClick={() => setSheetOpen(false)} aria-label="Close">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {preview.data.required_fields.length === 0 ? (
                <div className="rounded-2xl bg-teal-50 p-4 text-sm font-semibold text-teal-800">No extra details needed. Confirm to continue.</div>
              ) : null}
              {preview.data.required_fields.map((field) => (
                <label key={field.name} className="block">
                  <span className="label">{field.label}{field.required ? "" : " (optional)"}</span>
                  <input
                    className="field mt-2 h-14 rounded-2xl text-base"
                    type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
                    inputMode={field.type === "number" ? "numeric" : undefined}
                    value={values[field.name] ?? String(field.default ?? "")}
                    onChange={(event) => setValues((prev) => ({ ...prev, [field.name]: event.target.value }))}
                    required={field.required}
                  />
                </label>
              ))}
            </div>

            <div className="mt-5 rounded-2xl bg-slate-50 p-3 text-sm text-slate-700">
              Confirm updating <span className="font-mono font-bold">{po.po_number}</span> from {preview.data.current_stage.replaceAll("_", " ")} to {preview.data.next_stage.replaceAll("_", " ")}?
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <button type="button" className="min-h-14 rounded-2xl border border-slate-200 bg-white font-bold text-slate-700" onClick={() => setSheetOpen(false)}>Cancel</button>
              <button type="submit" className="primary-button min-h-14 rounded-2xl" disabled={execute.isPending}>{execute.isPending ? "Updating..." : "Confirm"}</button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-3 text-center shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-black text-slate-950">{value}</p>
    </div>
  );
}

function SmallAction({ icon: Icon, label }: { icon: typeof Pencil; label: string }) {
  return (
    <button type="button" className="flex min-h-14 items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700">
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}
