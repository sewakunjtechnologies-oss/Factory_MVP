import { type FormEvent, type ReactNode, useState } from "react";
import { CheckCircle2, PackageSearch, Send } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { LoadingState } from "../components/LoadingState";
import { useCreateFabricReceipt, useDebitNotes, useFabricReceipts, useFabricShortages, useSupplierReturns } from "../hooks/useFabric";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import { todayISO } from "../utils/forms";
import { formatDate, formatMeters, formatNumber } from "../utils/format";

export default function FabricPage() {
  const shortages = useFabricShortages();
  const receipts = useFabricReceipts();
  const returns = useSupplierReturns();
  const debitNotes = useDebitNotes();
  const pos = usePurchaseOrders();
  const createReceipt = useCreateFabricReceipt();
  const [values, setValues] = useState<Record<string, string>>({
    purchase_order_id: "",
    supplier_name: "",
    fabric_type: "",
    color: "",
    gsm: "",
    width: "",
    available_length_m: "",
    approximate_rolls: "",
    status: "approved",
    quality_notes: "",
    debit_amount: "",
    received_at: todayISO(),
  });

  if (shortages.isLoading) {
    return <LoadingState label="Loading fabric board" />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createReceipt.mutate({
      purchase_order_id: values.purchase_order_id || null,
      supplier_name: values.supplier_name,
      fabric_type: values.fabric_type,
      color: values.color,
      gsm: Number(values.gsm),
      width: Number(values.width),
      available_length_m: Number(values.available_length_m),
      approximate_rolls: values.approximate_rolls ? Number(values.approximate_rolls) : null,
      status: values.status as "approved" | "failed",
      quality_notes: values.quality_notes || null,
      debit_amount: values.debit_amount ? Number(values.debit_amount) : null,
      received_at: values.received_at,
    });
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,520px)_1fr]">
      <section className="panel p-5">
        <div className="flex items-center gap-2">
          <PackageSearch className="h-5 w-5 text-teal-700" aria-hidden="true" />
          <div>
            <h1 className="text-xl font-bold text-slate-950">Fabric Shortage / Receipt</h1>
            <p className="text-sm text-slate-500">Failed receipts create return and debit-note records; only approved fabric enters usable stock.</p>
          </div>
        </div>
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField id="purchase_order_id" label="PO" values={values} setValues={setValues} options={(pos.data ?? []).map((po) => [po.id, po.po_number])} />
            <SelectField id="status" label="Result" values={values} setValues={setValues} options={[["approved", "Approved"], ["failed", "Failed"]]} />
            <TextField id="supplier_name" label="Supplier" values={values} setValues={setValues} required />
            <TextField id="received_at" label="Received Date" values={values} setValues={setValues} type="date" required />
            <TextField id="fabric_type" label="Fabric Type" values={values} setValues={setValues} required />
            <TextField id="color" label="Color" values={values} setValues={setValues} required />
            <TextField id="gsm" label="GSM" values={values} setValues={setValues} type="number" required />
            <TextField id="width" label="Width" values={values} setValues={setValues} type="number" required />
            <TextField id="available_length_m" label="Received Meters" values={values} setValues={setValues} type="number" required />
            <TextField id="approximate_rolls" label="Approx Rolls" values={values} setValues={setValues} type="number" />
            {values.status === "failed" ? <TextField id="debit_amount" label="Debit Amount" values={values} setValues={setValues} type="number" /> : null}
          </div>
          <div className="space-y-2">
            <label className="label" htmlFor="quality_notes">Quality Notes</label>
            <textarea id="quality_notes" className="field min-h-24 py-2" value={values.quality_notes} onChange={(event) => setValues({ ...values, quality_notes: event.target.value })} />
          </div>
          {createReceipt.isError ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{getApiErrorMessage(createReceipt.error)}</div> : null}
          {createReceipt.isSuccess ? <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" />Receipt recorded.</div> : null}
          <button className="primary-button w-full" disabled={createReceipt.isPending}><Send className="h-4 w-4" />Record Receipt</button>
        </form>
      </section>
      <section className="space-y-5">
        <Panel title="Open Shortages">
          {(shortages.data ?? []).map((plan) => (
            <Row key={plan.id} left={`PO ${plan.purchase_order_id}`} right={`${formatMeters(plan.shortage_m)} short`} />
          ))}
        </Panel>
        <Panel title="Receipts">
          {(receipts.data ?? []).slice(0, 8).map((receipt) => (
            <Row key={receipt.id} left={`${receipt.supplier_name} · ${receipt.fabric_type}`} right={`${formatMeters(receipt.received_length_m)} · ${receipt.status}`} />
          ))}
        </Panel>
        <div className="grid gap-5 lg:grid-cols-2">
          <Panel title="Supplier Returns">
            {(returns.data ?? []).slice(0, 5).map((item) => <Row key={item.id} left={item.supplier_name} right={`${formatMeters(item.returned_length_m)} · ${formatDate(item.returned_at)}`} />)}
          </Panel>
          <Panel title="Debit Notes">
            {(debitNotes.data ?? []).slice(0, 5).map((item) => <Row key={item.id} left={item.supplier_name} right={item.amount ? formatNumber(Number(item.amount)) : "Recorded"} />)}
          </Panel>
        </div>
      </section>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return <div className="panel overflow-hidden"><div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-950">{title}</div><div className="divide-y divide-slate-100">{children || <div className="px-4 py-6 text-sm text-slate-500">Nothing pending.</div>}</div></div>;
}

function Row({ left, right }: { left: string; right: string }) {
  return <div className="flex items-center justify-between gap-4 px-4 py-3 text-sm"><span className="font-semibold text-slate-950">{left}</span><span className="text-slate-600">{right}</span></div>;
}

function TextField({ id, label, values, setValues, type = "text", required }: { id: string; label: string; values: Record<string, string>; setValues: (values: Record<string, string>) => void; type?: string; required?: boolean }) {
  return <div className="space-y-2"><label className="label" htmlFor={id}>{label}</label><input id={id} className="field" type={type} min={type === "number" ? "0" : undefined} value={values[id]} onChange={(event) => setValues({ ...values, [id]: event.target.value })} required={required} /></div>;
}

function SelectField({ id, label, values, setValues, options }: { id: string; label: string; values: Record<string, string>; setValues: (values: Record<string, string>) => void; options: string[][] }) {
  return <div className="space-y-2"><label className="label" htmlFor={id}>{label}</label><select id={id} className="field" value={values[id]} onChange={(event) => setValues({ ...values, [id]: event.target.value })}><option value="">Select</option>{options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>;
}
