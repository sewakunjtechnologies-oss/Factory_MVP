import { ClipboardPlus, Search } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getApiErrorMessage } from "../../api/axios";
import { LoadingState } from "../../components/LoadingState";
import { useCreateMobilePO, useMobileCategoryOptions } from "../../hooks/useMobileWorkflow";
import type { UUID } from "../../types/api";
import { formatMeters, formatNumber } from "../../utils/format";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function MobileCreatePOPage() {
  const navigate = useNavigate();
  const options = useMobileCategoryOptions();
  const createPO = useCreateMobilePO();
  const [query, setQuery] = useState("");
  const [categoryOptionId, setCategoryOptionId] = useState<UUID | "">("");
  const [quantity, setQuantity] = useState("");
  const [deliveryMode, setDeliveryMode] = useState<"month" | "date">("month");
  const [deliveryMonth, setDeliveryMonth] = useState(currentMonth());
  const [deliveryDate, setDeliveryDate] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = options.data ?? [];
    if (!q) return rows.slice(0, 40);
    return rows
      .filter((row) => [row.searchable_text, row.category_name, row.fabric_code].join(" ").toLowerCase().includes(q))
      .slice(0, 40);
  }, [options.data, query]);
  const selected = (options.data ?? []).find((row) => row.id === categoryOptionId);
  const qty = Math.max(0, Number(quantity || 0));
  const perPiece = Number(selected?.per_piece_meters ?? 0);
  const required = qty * perPiece;
  const available = Number(selected?.stock_meters ?? 0);
  const shortage = Math.max(0, required - available);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!categoryOptionId || qty <= 0) return;
    const po = await createPO.mutateAsync({
      category_option_id: categoryOptionId,
      quantity: qty,
      delivery_mode: deliveryMode,
      delivery_month: deliveryMode === "month" ? deliveryMonth : null,
      delivery_date: deliveryMode === "date" ? deliveryDate : null,
    });
    navigate(`/mobile/po/${po.id}`);
  }

  if (options.isLoading) return <LoadingState />;

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <header className="rounded-3xl bg-white p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-700">
            <ClipboardPlus className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-950">Create PO</h1>
            <p className="text-sm text-slate-500">Only category, quantity, and delivery.</p>
          </div>
        </div>
      </header>

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="label" htmlFor="category-search">Product / Fabric Category</label>
        <div className="relative mt-2">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <input
            id="category-search"
            className="field h-14 rounded-2xl pl-12 text-base"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search 69, Garden Bloom, 50X75..."
          />
        </div>
        <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
          {filtered.map((row) => (
            <button
              key={row.id}
              type="button"
              className={`w-full rounded-2xl border p-3 text-left ${categoryOptionId === row.id ? "border-teal-500 bg-teal-50" : "border-slate-200 bg-white"}`}
              onClick={() => setCategoryOptionId(row.id)}
            >
              <p className="font-mono text-sm font-bold text-slate-950">{row.fabric_code}</p>
              <p className="mt-1 text-xs text-slate-500">{row.category_name} · {Number(row.per_piece_meters).toFixed(2)} m/pc · stock {formatMeters(Number(row.stock_meters))} m</p>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="label" htmlFor="quantity">Quantity</label>
        <input
          id="quantity"
          className="field mt-2 h-14 rounded-2xl text-lg font-bold"
          type="number"
          min={1}
          step={1}
          inputMode="numeric"
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
          placeholder="8,000"
          required
        />
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="label">Delivery</p>
        <div className="mt-2 grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1">
          <button type="button" className={`rounded-xl px-3 py-3 text-sm font-bold ${deliveryMode === "month" ? "bg-white text-teal-800 shadow-sm" : "text-slate-500"}`} onClick={() => setDeliveryMode("month")}>Month</button>
          <button type="button" className={`rounded-xl px-3 py-3 text-sm font-bold ${deliveryMode === "date" ? "bg-white text-teal-800 shadow-sm" : "text-slate-500"}`} onClick={() => setDeliveryMode("date")}>Exact Date</button>
        </div>
        {deliveryMode === "month" ? (
          <input className="field mt-3 h-14 rounded-2xl" type="month" value={deliveryMonth} onChange={(event) => setDeliveryMonth(event.target.value)} required />
        ) : (
          <input className="field mt-3 h-14 rounded-2xl" type="date" value={deliveryDate} onChange={(event) => setDeliveryDate(event.target.value)} required />
        )}
      </section>

      {selected && qty > 0 ? (
        <section className={`rounded-3xl border p-4 shadow-sm ${shortage > 0 ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}>
          <p className="text-sm font-black text-slate-950">Fabric check preview</p>
          <p className="mt-2 text-sm text-slate-700">
            {formatNumber(qty)} pcs need about {formatMeters(required)} m. Available is {formatMeters(available)} m.
          </p>
          <p className={`mt-2 font-bold ${shortage > 0 ? "text-amber-800" : "text-emerald-800"}`}>
            {shortage > 0 ? `Short by ${formatMeters(shortage)} m` : "Fabric is available"}
          </p>
        </section>
      ) : null}

      {createPO.isError ? <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{getApiErrorMessage(createPO.error)}</div> : null}

      <button type="submit" className="primary-button min-h-14 w-full rounded-2xl text-base" disabled={!categoryOptionId || qty <= 0 || createPO.isPending}>
        {createPO.isPending ? "Creating..." : "Create PO and Check Fabric"}
      </button>
    </form>
  );
}
