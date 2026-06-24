import { type FormEvent, useEffect, useMemo, useState } from "react";
import { BarChart3, Boxes, Plus, RefreshCcw, Search, Trash2 } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import {
  useBackfillJunePackingMaterials,
  useCreatePackingMaterial,
  useDeletePackingMaterial,
  usePackingMaterialCategoryDemand,
  usePackingMaterials,
  useUpdatePackingMaterial,
} from "../hooks/usePackingMaterials";
import { useAuthStore } from "../store/authStore";
import type { PackingMaterialRead, PackingMaterialStatus } from "../types/api";
import { formatDate, formatNumber } from "../utils/format";

const STATUS_OPTIONS: PackingMaterialStatus[] = ["in_stock", "ordered", "received", "shortage", "consumed", "unknown"];

const emptyForm = {
  category_name: "",
  material_name: "",
  material_type: "other",
  unit: "pcs",
  required_qty: "",
  in_stock_qty: "",
  ordered_qty: "",
  received_qty: "",
  consumed_qty: "",
  printed_consumption_qty: "",
  actual_consumption_qty: "",
  printed_stock_qty: "",
  actual_stock_qty: "",
  supplier_name: "",
  expected_delivery_date: "",
  notes: "",
};

export default function PackingMaterialsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const user = useAuthStore((state) => state.user);
  const isOwner = user?.role === "owner";
  const materialsQuery = usePackingMaterials({ search: search || undefined, status: status || undefined });
  const categoryDemand = usePackingMaterialCategoryDemand(isOwner);
  const createMaterial = useCreatePackingMaterial();
  const updateMaterial = useUpdatePackingMaterial();
  const deleteMaterial = useDeletePackingMaterial();
  const backfillJune = useBackfillJunePackingMaterials();

  const rows = useMemo(() => materialsQuery.data ?? [], [materialsQuery.data]);
  const totals = useMemo(
    () =>
      rows.reduce(
        (acc, row) => {
          acc.required += num(row.required_qty);
          acc.inStock += num(row.actual_stock_qty || row.in_stock_qty);
          acc.ordered += num(row.ordered_qty);
          acc.shortage += num(row.shortage_qty);
          acc.printedConsumption += num(row.printed_consumption_qty || row.required_qty);
          acc.actualConsumption += num(row.actual_consumption_qty || row.consumed_qty);
          acc.printedStock += num(row.printed_stock_qty || row.in_stock_qty);
          return acc;
        },
        { required: 0, inStock: 0, ordered: 0, shortage: 0, printedConsumption: 0, actualConsumption: 0, printedStock: 0 },
      ),
    [rows],
  );

  if (materialsQuery.isLoading) return <LoadingState label="Loading packing material inventory" />;

  function remove(row: PackingMaterialRead) {
    const ok = window.confirm(`Delete ${row.material_name} for ${row.po_number ?? row.category_name}?`);
    if (!ok) return;
    deleteMaterial.mutate(row.id);
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Boxes className="h-5 w-5 text-teal-700" aria-hidden="true" />
            <div>
              <h1 className="text-xl font-bold text-slate-950">Packing Material Inventory</h1>
              <p className="text-sm text-slate-500">
                Category-wise tags, headers, inserts, stiffeners and bags for each June PO.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="secondary-button" onClick={() => backfillJune.mutate()} disabled={backfillJune.isPending}>
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              {backfillJune.isPending ? "Generating…" : "Generate June materials"}
            </button>
            <button type="button" className="primary-button" onClick={() => setShowCreate((value) => !value)}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add material
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              className="field pl-9"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search PO, category or material"
              aria-label="Search packing materials"
            />
          </label>
          <select className="field" value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter status">
            <option value="">All status</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>{statusLabel(option)}</option>
            ))}
          </select>
        </div>

        <div className="mt-5 grid gap-3 grid-cols-2 xl:grid-cols-6">
          <StatCard label="Required" value={formatQty(totals.required)} />
          {isOwner ? (
            <>
              <StatCard label="Printed stock" value={formatQty(totals.printedStock)} />
              <StatCard label="Actual stock" value={formatQty(totals.inStock)} tone="success" />
              <StatCard label="Printed consumption" value={formatQty(totals.printedConsumption)} />
              <StatCard label="Actual consumption" value={formatQty(totals.actualConsumption)} />
            </>
          ) : (
            <StatCard label="In stock" value={formatQty(totals.inStock)} tone="success" />
          )}
          <StatCard label="Ordered" value={formatQty(totals.ordered)} />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <StatCard label="Shortage" value={formatQty(totals.shortage)} tone={totals.shortage > 0 ? "alert" : undefined} />
          <StatCard label="Packing planner check" value={totals.shortage > 0 ? "Material risk open" : "Material ready"} tone={totals.shortage > 0 ? "alert" : "success"} />
        </div>

        {backfillJune.data ? (
          <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            Generated packing materials for {backfillJune.data.purchase_orders_scanned} June POs: {backfillJune.data.rows_created} created, {backfillJune.data.rows_updated} updated.
          </div>
        ) : null}
        {backfillJune.isError || updateMaterial.isError || createMaterial.isError || deleteMaterial.isError ? (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {getApiErrorMessage(backfillJune.error ?? updateMaterial.error ?? createMaterial.error ?? deleteMaterial.error)}
          </div>
        ) : null}
      </section>

      {isOwner ? (
        <section className="panel p-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-teal-700" aria-hidden="true" />
            <div>
              <h2 className="text-base font-bold text-slate-950">Owner category order summary</h2>
              <p className="text-sm text-slate-500">Calculated from previous PO data to show which categories are getting more orders.</p>
            </div>
          </div>
          {categoryDemand.isLoading ? (
            <p className="mt-4 text-sm text-slate-500">Loading category demand…</p>
          ) : categoryDemand.data?.length ? (
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {categoryDemand.data.slice(0, 6).map((item) => (
                <div key={item.category} className="rounded-md border border-slate-200 bg-white p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{item.category}</p>
                  <p className="mt-1 text-lg font-bold text-slate-950">{formatNumber(item.total_pieces)} pcs</p>
                  <p className="text-xs text-slate-500">{item.order_count} PO{item.order_count === 1 ? "" : "s"} · {ruleLabel(item.material_rule)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">No category demand data found yet.</p>
          )}
        </section>
      ) : null}

      {showCreate ? (
        <CreateMaterialForm
          busy={createMaterial.isPending}
          showOwnerFields={isOwner}
          onSubmit={async (payload) => {
            await createMaterial.mutateAsync(payload);
            setShowCreate(false);
          }}
        />
      ) : null}

      {rows.length === 0 ? (
        <EmptyState icon={Boxes} title="No packing material rows" message="Generate June materials or add rows manually." />
      ) : (
        <section className="panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-3">PO / Category</th>
                  <th className="px-3 py-3">Material</th>
                  <th className="px-3 py-3 text-right">Required</th>
                  {isOwner ? (
                    <>
                      <th className="px-3 py-3 text-right">Printed cons.</th>
                      <th className="px-3 py-3 text-right">Actual cons.</th>
                      <th className="px-3 py-3 text-right">Printed stock</th>
                      <th className="px-3 py-3 text-right">Actual stock</th>
                    </>
                  ) : (
                    <>
                      <th className="px-3 py-3 text-right">In stock</th>
                      <th className="px-3 py-3 text-right">Consumed</th>
                    </>
                  )}
                  <th className="px-3 py-3 text-right">Ordered</th>
                  <th className="px-3 py-3 text-right">Received</th>
                  <th className="px-3 py-3 text-right">Short</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Supplier</th>
                  <th className="px-3 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr key={row.id} className="align-middle">
                    <td className="px-3 py-3">
                      <p className="whitespace-nowrap font-semibold text-slate-950">{row.po_number ?? "Manual"}</p>
                      <p className="max-w-[18rem] truncate text-xs text-slate-500" title={row.category_name}>{row.category_name}</p>
                    </td>
                    <td className="px-3 py-3">
                      <p className="whitespace-nowrap font-semibold text-slate-800">{row.material_name}</p>
                      <p className="text-xs text-slate-500">{row.material_type} · {row.unit}</p>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <EditableQty value={row.required_qty} onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { required_qty: value } })} />
                    </td>
                    {isOwner ? (
                      <>
                        <td className="px-3 py-3 text-right">
                          <EditableQty value={row.printed_consumption_qty} onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { printed_consumption_qty: value } })} />
                        </td>
                        <td className="px-3 py-3 text-right">
                          <EditableQty value={row.actual_consumption_qty} onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { actual_consumption_qty: value } })} />
                        </td>
                        <td className="px-3 py-3 text-right">
                          <EditableQty value={row.printed_stock_qty} onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { printed_stock_qty: value } })} />
                        </td>
                        <td className="px-3 py-3 text-right">
                          <EditableQty value={row.actual_stock_qty} tone="success" onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { actual_stock_qty: value } })} />
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-3 py-3 text-right">
                          <EditableQty value={row.in_stock_qty} tone="success" onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { in_stock_qty: value } })} />
                        </td>
                        <td className="px-3 py-3 text-right">
                          <EditableQty value={row.consumed_qty} onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { consumed_qty: value } })} />
                        </td>
                      </>
                    )}
                    <td className="px-3 py-3 text-right">
                      <EditableQty value={row.ordered_qty} onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { ordered_qty: value } })} />
                    </td>
                    <td className="px-3 py-3 text-right">
                      <EditableQty value={row.received_qty} onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { received_qty: value } })} />
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span className={num(row.shortage_qty) > 0 ? "font-bold text-red-700" : "text-slate-400"}>
                        {num(row.shortage_qty) > 0 ? formatQty(num(row.shortage_qty)) : "—"}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <select
                        className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold"
                        value={row.status}
                        onChange={(event) => updateMaterial.mutate({ id: row.id, payload: { status: event.target.value as PackingMaterialStatus } })}
                      >
                        {STATUS_OPTIONS.map((option) => (
                          <option key={option} value={option}>{statusLabel(option)}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-3">
                      <EditableText
                        value={row.supplier_name ?? ""}
                        placeholder="Supplier"
                        onCommit={(value) => updateMaterial.mutate({ id: row.id, payload: { supplier_name: value || null } })}
                      />
                      {row.expected_delivery_date ? (
                        <p className="mt-1 text-[11px] text-slate-500">ETA {formatDate(row.expected_delivery_date)}</p>
                      ) : null}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <button type="button" className="chip-button text-red-700" onClick={() => remove(row)} disabled={deleteMaterial.isPending}>
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function CreateMaterialForm({
  busy,
  showOwnerFields,
  onSubmit,
}: {
  busy: boolean;
  showOwnerFields: boolean;
  onSubmit: (payload: {
    category_name: string;
    material_name: string;
    material_type: string;
    unit: string;
    required_qty: number;
    in_stock_qty: number;
    ordered_qty: number;
    received_qty: number;
    consumed_qty: number;
    printed_consumption_qty?: number;
    actual_consumption_qty?: number;
    printed_stock_qty?: number;
    actual_stock_qty?: number;
    supplier_name: string | null;
    expected_delivery_date: string | null;
    notes: string | null;
  }) => Promise<void>;
}) {
  const [values, setValues] = useState(emptyForm);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = {
      category_name: values.category_name.trim(),
      material_name: values.material_name.trim(),
      material_type: values.material_type.trim() || "other",
      unit: values.unit.trim() || "pcs",
      required_qty: Number(values.required_qty) || 0,
      in_stock_qty: Number(values.in_stock_qty) || 0,
      ordered_qty: Number(values.ordered_qty) || 0,
      received_qty: Number(values.received_qty) || 0,
      consumed_qty: Number(values.consumed_qty) || 0,
      supplier_name: values.supplier_name.trim() || null,
      expected_delivery_date: values.expected_delivery_date || null,
      notes: values.notes.trim() || null,
    };
    void onSubmit({
      ...payload,
      ...(showOwnerFields
        ? {
            printed_consumption_qty: Number(values.printed_consumption_qty) || Number(values.required_qty) || 0,
            actual_consumption_qty: Number(values.actual_consumption_qty) || Number(values.consumed_qty) || 0,
            printed_stock_qty: Number(values.printed_stock_qty) || Number(values.in_stock_qty) || 0,
            actual_stock_qty: Number(values.actual_stock_qty) || Number(values.in_stock_qty) || 0,
          }
        : {}),
    });
  }

  function setField(field: keyof typeof emptyForm, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  return (
    <section className="panel p-5">
      <h2 className="text-base font-bold text-slate-950">Add packing material</h2>
      <form className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" onSubmit={submit}>
        <Field id="pm-category" label="Category" value={values.category_name} onChange={(value) => setField("category_name", value)} required />
        <Field id="pm-material" label="Material" value={values.material_name} onChange={(value) => setField("material_name", value)} required />
        <Field id="pm-type" label="Type" value={values.material_type} onChange={(value) => setField("material_type", value)} />
        <Field id="pm-unit" label="Unit" value={values.unit} onChange={(value) => setField("unit", value)} />
        <Field id="pm-required" label="Required" value={values.required_qty} onChange={(value) => setField("required_qty", value)} type="number" />
        {showOwnerFields ? (
          <>
            <Field id="pm-printed-consumption" label="Printed consumption" value={values.printed_consumption_qty} onChange={(value) => setField("printed_consumption_qty", value)} type="number" />
            <Field id="pm-actual-consumption" label="Actual consumption" value={values.actual_consumption_qty} onChange={(value) => setField("actual_consumption_qty", value)} type="number" />
            <Field id="pm-printed-stock" label="Printed stock" value={values.printed_stock_qty} onChange={(value) => setField("printed_stock_qty", value)} type="number" />
            <Field id="pm-actual-stock" label="Actual stock" value={values.actual_stock_qty} onChange={(value) => setField("actual_stock_qty", value)} type="number" />
          </>
        ) : null}
        <Field id="pm-stock" label="Legacy stock" value={values.in_stock_qty} onChange={(value) => setField("in_stock_qty", value)} type="number" />
        <Field id="pm-ordered" label="Ordered" value={values.ordered_qty} onChange={(value) => setField("ordered_qty", value)} type="number" />
        <Field id="pm-received" label="Received" value={values.received_qty} onChange={(value) => setField("received_qty", value)} type="number" />
        <Field id="pm-consumed" label="Legacy consumed" value={values.consumed_qty} onChange={(value) => setField("consumed_qty", value)} type="number" />
        <Field id="pm-supplier" label="Supplier" value={values.supplier_name} onChange={(value) => setField("supplier_name", value)} />
        <Field id="pm-eta" label="Expected delivery" value={values.expected_delivery_date} onChange={(value) => setField("expected_delivery_date", value)} type="date" />
        <Field id="pm-notes" label="Notes" value={values.notes} onChange={(value) => setField("notes", value)} />
        <div className="flex items-end lg:col-span-4">
          <button type="submit" className="primary-button" disabled={busy || !values.category_name.trim() || !values.material_name.trim()}>
            {busy ? "Saving…" : "Save material"}
          </button>
        </div>
      </form>
    </section>
  );
}

function EditableQty({ value, tone, onCommit }: { value: string; tone?: "success"; onCommit: (value: number) => void }) {
  const numeric = num(value);
  const [draft, setDraft] = useState(numeric.toFixed(3));

  useEffect(() => {
    setDraft(numeric.toFixed(3));
  }, [numeric]);

  function commit() {
    const parsed = Number(draft);
    if (!Number.isFinite(parsed) || parsed < 0) {
      setDraft(numeric.toFixed(3));
      return;
    }
    if (Math.abs(parsed - numeric) < 0.0005) return;
    onCommit(parsed);
  }

  return (
    <input
      type="number"
      min={0}
      step="0.001"
      inputMode="decimal"
      className={`h-8 w-24 rounded-md border border-slate-200 bg-white px-2 text-right text-xs font-semibold tabular-nums outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100 ${tone === "success" ? "text-emerald-700" : "text-slate-700"}`}
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
    />
  );
}

function EditableText({ value, placeholder, onCommit }: { value: string; placeholder: string; onCommit: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return (
    <input
      className="h-8 w-36 rounded-md border border-slate-200 bg-white px-2 text-xs outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100"
      value={draft}
      placeholder={placeholder}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => {
        if (draft !== value) onCommit(draft.trim());
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
    />
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  type = "text",
  required,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <div className="space-y-2">
      <label className="label" htmlFor={id}>{label}</label>
      <input
        id={id}
        className="field"
        type={type}
        min={type === "number" ? "0" : undefined}
        step={type === "number" ? "0.001" : undefined}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
      />
    </div>
  );
}

function StatCard({ label, value, tone }: { label: string; value: string; tone?: "success" | "alert" }) {
  const valueClass = tone === "alert" ? "text-red-700" : tone === "success" ? "text-emerald-700" : "text-slate-950";
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 truncate text-xl font-bold tabular-nums ${valueClass}`}>{value}</p>
    </div>
  );
}

function statusLabel(status: PackingMaterialStatus): string {
  return status.replace("_", " ");
}

function ruleLabel(rule: string): string {
  if (rule === "insert_stiffener_bag") return "Insert + stiffener + bag";
  if (rule === "header") return "Header";
  if (rule === "tag") return "Tag";
  return rule.replaceAll("_", " ");
}

function num(value: string | number | null | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatQty(value: number): string {
  return formatNumber(Number(value.toFixed(3)));
}
