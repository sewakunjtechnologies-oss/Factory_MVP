import { type FormEvent, useState } from "react";
import { Loader2, Save, X } from "lucide-react";

import { useUpdatePurchaseOrder } from "../hooks/usePurchaseOrders";
import type { PurchaseOrderRead } from "../types/api";

const STATUS_OPTIONS = [
  "draft",
  "fabric_check_pending",
  "fabric_ready",
  "shortage",
  "cutting",
  "stitching",
  "packing",
  "dispatch",
  "partially_dispatched",
  "completed",
  "delayed",
  "cancelled",
] as const;

export function POEditDialog({ po, onClose, onSaved }: { po: PurchaseOrderRead; onClose: () => void; onSaved: () => void }) {
  const update = useUpdatePurchaseOrder();

  const [poNumber, setPoNumber] = useState(po.po_number);
  const [orderQty, setOrderQty] = useState(String(po.order_quantity_pcs));
  const [mrp, setMrp] = useState(po.mrp ?? "");
  const [sellingPrice, setSellingPrice] = useState(po.selling_price ?? "");
  const [orderDate, setOrderDate] = useState(po.order_date);
  const [promiseDate, setPromiseDate] = useState(po.promise_delivery_date);
  const [actualDate, setActualDate] = useState(po.actual_delivery_date ?? "");
  const [status, setStatus] = useState<string>(po.status);
  const [notes, setNotes] = useState(po.notes ?? "");
  const [productFabricCategory, setProductFabricCategory] = useState(po.design_code_snapshot ?? po.design_name_snapshot ?? "");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const payload = {
      po_number: poNumber.trim(),
      order_quantity_pcs: Number(orderQty),
      mrp: mrp === "" ? null : Number(mrp),
      selling_price: sellingPrice === "" ? null : Number(sellingPrice),
      order_date: orderDate,
      promise_delivery_date: promiseDate,
      actual_delivery_date: actualDate || null,
      status,
      notes: notes.trim() || null,
      design_name_snapshot: productFabricCategory.trim() || null,
      design_code_snapshot: productFabricCategory.trim() || null,
    };
    try {
      await update.mutateAsync({ id: po.id, payload });
      onSaved();
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(e.response?.data?.detail ?? e.message ?? "Could not save.");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center overflow-y-auto bg-slate-900/40 p-4 sm:items-center" role="dialog" aria-modal="true">
      <div className="panel my-4 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h3 className="text-base font-bold text-slate-950">Edit purchase order</h3>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-slate-500 hover:bg-slate-100" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </header>

        <form className="space-y-4 px-5 py-4" onSubmit={handleSubmit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="po_number" label="PO number" value={poNumber} onChange={setPoNumber} required />
            <Field id="status" label="Status" value={status} onChange={setStatus} as="select" options={STATUS_OPTIONS as readonly string[]} />

            <Field id="order_qty" label="Quantity (pieces)" value={orderQty} onChange={setOrderQty} type="number" min={1} required />
            <Field id="mrp" label="MRP" value={String(mrp)} onChange={(v) => setMrp(v)} type="number" />

            <Field id="order_date" label="Order date" value={orderDate} onChange={setOrderDate} type="date" required />
            <Field id="promise_date" label="Promised delivery" value={promiseDate} onChange={setPromiseDate} type="date" required />

            <Field id="actual_date" label="Actual delivery (if done)" value={actualDate} onChange={setActualDate} type="date" />
            <Field id="selling" label="Selling price" value={String(sellingPrice)} onChange={(v) => setSellingPrice(v)} type="number" />

            <Field id="product_fabric_category" label="Product / Fabric Category" value={productFabricCategory} onChange={setProductFabricCategory} maxLength={180} />
          </div>

          <div className="space-y-2">
            <label className="label" htmlFor="notes">Notes</label>
            <textarea
              id="notes"
              className="field min-h-20 py-2"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
            />
          </div>

          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          ) : null}

          <footer className="flex flex-col-reverse gap-2 border-t border-slate-200 pt-4 sm:flex-row sm:justify-end">
            <button type="button" className="secondary-button" onClick={onClose} disabled={update.isPending}>
              Cancel
            </button>
            <button type="submit" className="primary-button" disabled={update.isPending}>
              {update.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {update.isPending ? "Saving…" : "Save changes"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}

type FieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  min?: number;
  maxLength?: number;
  as?: "input" | "select";
  options?: readonly string[];
};

function Field({ id, label, value, onChange, type = "text", required, min, maxLength, as = "input", options }: FieldProps) {
  return (
    <div className="space-y-2">
      <label className="label" htmlFor={id}>{label}</label>
      {as === "select" ? (
        <select id={id} className="field" value={value} onChange={(e) => onChange(e.target.value)} required={required}>
          {(options ?? []).map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          className="field"
          type={type}
          value={value}
          required={required}
          min={min}
          maxLength={maxLength}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </div>
  );
}
