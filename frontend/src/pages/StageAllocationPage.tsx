import { type FormEvent, useMemo, useState } from "react";
import { Network, Send } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { LoadingState } from "../components/LoadingState";
import { useContractors } from "../hooks/useContractors";
import { useAllocations, useCreateStageAllocation } from "../hooks/useProduction";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import type { StageName } from "../types/api";
import { productionStages } from "../utils/factoryMetrics";
import { formatDate, formatNumber, stageShortName } from "../utils/format";

export default function StageAllocationPage() {
  const pos = usePurchaseOrders();
  const contractors = useContractors();
  const [values, setValues] = useState({ purchase_order_id: "", stage: "cutting" as StageName, contractor_id: "", issued_qty: "", expected_completion_date: "", notes: "" });
  const allocations = useAllocations(values.purchase_order_id || undefined);
  const createAllocation = useCreateStageAllocation(values.purchase_order_id);
  const selectedPO = pos.data?.find((po) => po.id === values.purchase_order_id);
  const selectedStage = selectedPO?.stage_summaries.find((stage) => stage.stage === values.stage);
  const allocatedForStage = (allocations.data ?? []).filter((item) => item.stage === values.stage).reduce((sum, item) => sum + item.issued_qty, 0);
  const remaining = Math.max((selectedStage?.input_qty ?? 0) - allocatedForStage, 0);
  const contractorNameById = useMemo(() => new Map((contractors.data ?? []).map((contractor) => [contractor.id, contractor.name])), [contractors.data]);

  if (pos.isLoading) {
    return <LoadingState label="Loading allocation board" />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedStage) return;
    createAllocation.mutate({
      stage_summary_id: selectedStage.id,
      contractor_id: values.contractor_id,
      issued_qty: Number(values.issued_qty),
      expected_completion_date: values.expected_completion_date || null,
      notes: values.notes || null,
    });
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,520px)_1fr]">
      <section className="panel p-5">
        <div className="flex items-center gap-2"><Network className="h-5 w-5 text-teal-700" /><div><h1 className="text-xl font-bold text-slate-950">Stage Allocation</h1><p className="text-sm text-slate-500">Split each stage across multiple contractors with stage-specific targets.</p></div></div>
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <Select label="PO" value={values.purchase_order_id} onChange={(purchase_order_id) => setValues({ ...values, purchase_order_id, contractor_id: "" })} options={(pos.data ?? []).map((po) => [po.id, po.po_number])} />
          <Select label="Stage" value={values.stage} onChange={(stage) => setValues({ ...values, stage: stage as StageName })} options={productionStages.map((stage) => [stage, stageShortName(stage)])} />
          <Select label="Contractor" value={values.contractor_id} onChange={(contractor_id) => setValues({ ...values, contractor_id })} options={(contractors.data ?? []).map((contractor) => [contractor.id, contractor.name])} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Assign Qty" value={values.issued_qty} onChange={(issued_qty) => setValues({ ...values, issued_qty })} type="number" max={remaining || undefined} />
            <Input label="Target Return" value={values.expected_completion_date} onChange={(expected_completion_date) => setValues({ ...values, expected_completion_date })} type="date" />
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">Stage input {formatNumber(selectedStage?.input_qty ?? 0)} · allocated {formatNumber(allocatedForStage)} · remaining {formatNumber(remaining)}</div>
          {createAllocation.isError ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{getApiErrorMessage(createAllocation.error)}</div> : null}
          <button className="primary-button w-full" disabled={createAllocation.isPending || !selectedStage || Number(values.issued_qty) <= 0 || Number(values.issued_qty) > remaining}><Send className="h-4 w-4" />Create Allocation</button>
        </form>
      </section>
      <section className="panel overflow-hidden">
        <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-950">Contractor Workload</div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Contractor</th><th className="px-4 py-3">Stage</th><th className="px-4 py-3">Issued</th><th className="px-4 py-3">Completed</th><th className="px-4 py-3">Target</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{(allocations.data ?? []).map((allocation) => <tr key={allocation.id}><td className="px-4 py-3 font-semibold text-slate-950">{contractorNameById.get(allocation.contractor_id) ?? "Contractor"}</td><td className="px-4 py-3">{stageShortName(allocation.stage)}</td><td className="px-4 py-3">{formatNumber(allocation.issued_qty)}</td><td className="px-4 py-3">{formatNumber(allocation.completed_qty)}</td><td className="px-4 py-3">{formatDate(allocation.expected_completion_date)}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) {
  return <div className="space-y-2"><label className="label">{label}</label><select className="field" value={value} onChange={(event) => onChange(event.target.value)} required><option value="">Select</option>{options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}</select></div>;
}

function Input({ label, value, onChange, type = "text", max }: { label: string; value: string; onChange: (value: string) => void; type?: string; max?: number }) {
  return <div className="space-y-2"><label className="label">{label}</label><input className="field" type={type} min={type === "number" ? "0" : undefined} max={max} value={value} onChange={(event) => onChange(event.target.value)} required /></div>;
}
