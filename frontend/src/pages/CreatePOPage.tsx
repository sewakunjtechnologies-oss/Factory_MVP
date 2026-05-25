import { type FormEvent, useEffect, useMemo, useState } from "react";
import { ClipboardPlus, Send } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getApiErrorMessage } from "../api/axios";
import { useProductFabricLines } from "../hooks/useProductFabricLines";
import { useCreatePurchaseOrder, useProducts } from "../hooks/usePurchaseOrders";
import type { ProductRead, UUID } from "../types/api";
import { todayISO } from "../utils/forms";
import { formatMeters, formatNumber } from "../utils/format";

const CATEGORY_PRODUCT_KIND = "category";

function num(v: string | number | null | undefined): number {
  return v == null ? 0 : Number(v);
}

function leadingMrpFrom(name: string): number | null {
  const match = name.match(/^\d+/);
  return match ? Number(match[0]) : null;
}

export default function CreatePOPage() {
  const navigate = useNavigate();
  const productsQuery = useProducts();
  const createPO = useCreatePurchaseOrder();

  const categories = useMemo<ProductRead[]>(
    () => (productsQuery.data ?? [])
      .filter((p) => p.product_category === CATEGORY_PRODUCT_KIND)
      .sort((a, b) => a.product_name.localeCompare(b.product_name)),
    [productsQuery.data],
  );

  const [poNumber, setPoNumber] = useState<string>("");
  const [poNumberTouched, setPoNumberTouched] = useState(false);
  const [categoryId, setCategoryId] = useState<UUID | "">("");
  const [fabricCode, setFabricCode] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");
  const [shipmentDate, setShipmentDate] = useState<string>(todayISO());
  const [notes, setNotes] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);

  // Default to first category once products load.
  useEffect(() => {
    if (!categoryId && categories.length > 0) {
      setCategoryId(categories[0].id);
    }
  }, [categories, categoryId]);

  const linesQuery = useProductFabricLines(categoryId || undefined);
  const lines = linesQuery.data ?? [];

  // Reset fabric when category changes so we never display a fabric that doesn't belong.
  useEffect(() => {
    setFabricCode("");
  }, [categoryId]);

  // Helpful prefill: until the user types into the PO number field, seed it with
  // "{category}-{fabric}-" so all they need to add is the size + code suffix from
  // the dispatch sheet. The full string is theirs to finalise — we never auto-commit.
  const selectedCategoryName = categories.find((p) => p.id === categoryId)?.product_name ?? "";
  useEffect(() => {
    if (poNumberTouched) return;
    if (!selectedCategoryName || !fabricCode) {
      setPoNumber("");
      return;
    }
    setPoNumber(`${selectedCategoryName}-${fabricCode}-`);
  }, [selectedCategoryName, fabricCode, poNumberTouched]);

  const selectedCategory = categories.find((p) => p.id === categoryId);
  const selectedFabric = lines.find((l) => l.fabric_code === fabricCode);
  const wastagePercent = selectedCategory ? num(selectedCategory.wastage_percent) : 0;
  const perPiece = selectedFabric ? num(selectedFabric.per_piece_meters) : 0;
  const fabricOnHandMtrs = selectedFabric ? num(selectedFabric.stock_meters) : 0;
  const piecesAvailableInStock = selectedFabric ? selectedFabric.pieces_in_stock : 0;
  const qtyNum = Math.max(0, num(quantity));

  // Step 1: pieces already in stock can fulfill part of the PO directly.
  const piecesFromStock = Math.min(piecesAvailableInStock, qtyNum);
  const piecesToMake = Math.max(0, qtyNum - piecesFromStock);

  // Step 2: only the pieces we still need to make consume fabric.
  const baseConsumption = piecesToMake * perPiece;
  const consumptionWithWastage = baseConsumption * (1 + wastagePercent / 100);
  const wastageMeters = consumptionWithWastage - baseConsumption;

  // Step 3: do we have enough fabric on hand for the remaining pieces?
  const fabricShortageMtrs = Math.max(0, consumptionWithWastage - fabricOnHandMtrs);

  const trimmedPoNumber = poNumber.trim();
  const canSubmit = Boolean(
    selectedCategory && selectedFabric && qtyNum > 0 && shipmentDate && trimmedPoNumber && !createPO.isPending,
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!trimmedPoNumber) {
      setFormError("Enter a PO number (the full SKU from the dispatch sheet).");
      return;
    }
    if (!selectedCategory || !selectedFabric) {
      setFormError("Pick a category and fabric to continue.");
      return;
    }
    if (qtyNum <= 0) {
      setFormError("Quantity must be greater than zero.");
      return;
    }

    const today = todayISO();
    const fabricLabel = selectedFabric.fabric_code;

    const po = await createPO.mutateAsync({
      po_number: trimmedPoNumber,
      product_id: selectedCategory.id,
      order_quantity_pcs: qtyNum,
      mrp: leadingMrpFrom(selectedCategory.product_name),
      order_date: today,
      promise_delivery_date: shipmentDate,
      notes: notes.trim() || null,
      // Persist the chosen fabric variant on the PO so the workflow downstream knows
      // which fabric line under the category this order draws from.
      custom_design_name: fabricLabel,
      save_custom_design_to_library: false,
    });

    navigate(`/po/${po.id}`);
  }

  return (
    <section className="panel mx-auto max-w-3xl p-6">
      <header className="flex items-start gap-3 border-b border-slate-100 pb-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-teal-50 text-teal-700">
          <ClipboardPlus className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h1 className="text-xl font-bold text-slate-950">Create purchase order</h1>
          <p className="mt-0.5 text-sm text-slate-500">PO number comes from the dispatch sheet — pick the category and fabric, then fill in the size + code suffix.</p>
        </div>
      </header>

      <form className="mt-5 space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label className="label" htmlFor="po-number">PO number</label>
          <input
            id="po-number"
            type="text"
            className="field font-mono"
            value={poNumber}
            onChange={(e) => {
              setPoNumberTouched(true);
              setPoNumber(e.target.value);
            }}
            placeholder="e.g. 199-BEIGE-DMASK-140X215-PL-TIR-10-26"
            maxLength={150}
            required
            spellCheck={false}
            autoComplete="off"
          />
          <p className="text-xs text-slate-500">
            We pre-fill the category and fabric prefix once you pick them below — just add the size + code from the sheet. Must be unique.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="label" htmlFor="category">Category</label>
            <select
              id="category"
              className="field"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value as UUID | "")}
              required
              disabled={productsQuery.isLoading}
            >
              <option value="">Select category</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.product_name}</option>
              ))}
            </select>
            {productsQuery.isLoading ? <p className="text-xs text-slate-500">Loading categories…</p> : null}
          </div>

          <div className="space-y-2">
            <label className="label" htmlFor="fabric">Fabric</label>
            <select
              id="fabric"
              className="field"
              value={fabricCode}
              onChange={(e) => setFabricCode(e.target.value)}
              required
              disabled={!categoryId || linesQuery.isLoading}
            >
              <option value="">{!categoryId ? "Pick a category first" : "Select fabric"}</option>
              {lines
                .slice()
                .sort((a, b) => a.fabric_code.localeCompare(b.fabric_code))
                .map((l) => (
                  <option key={l.id} value={l.fabric_code}>
                    {l.fabric_code} ({num(l.per_piece_meters).toFixed(2)} m/pc)
                  </option>
                ))}
            </select>
            {categoryId && !linesQuery.isLoading && lines.length === 0 ? (
              <p className="text-xs text-amber-700">This category has no fabric variants yet. Add some on the Fabric Lines page.</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <label className="label" htmlFor="qty">Quantity (pieces)</label>
            <input
              id="qty"
              className="field"
              type="number"
              min={1}
              step={1}
              inputMode="numeric"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <label className="label" htmlFor="shipment">Shipment date</label>
            <input
              id="shipment"
              className="field"
              type="date"
              value={shipmentDate}
              min={todayISO()}
              onChange={(e) => setShipmentDate(e.target.value)}
              required
            />
            <p className="text-xs text-slate-500">Order date = today ({todayISO()}) is set automatically.</p>
          </div>
        </div>

        <div className="space-y-2">
          <label className="label" htmlFor="notes">Notes (optional)</label>
          <textarea
            id="notes"
            className="field min-h-20 py-2"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Anything the floor should know about this PO"
          />
        </div>

        <ConsumptionPreview
          category={selectedCategory}
          fabricCode={fabricCode}
          perPiece={perPiece}
          quantity={qtyNum}
          piecesFromStock={piecesFromStock}
          piecesToMake={piecesToMake}
          piecesAvailableInStock={piecesAvailableInStock}
          baseConsumption={baseConsumption}
          wastageMeters={wastageMeters}
          wastagePercent={wastagePercent}
          totalConsumption={consumptionWithWastage}
          fabricOnHandMtrs={fabricOnHandMtrs}
          fabricShortageMtrs={fabricShortageMtrs}
        />

        {formError ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</div>
        ) : null}
        {createPO.isError ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {getApiErrorMessage(createPO.error)}
          </div>
        ) : null}

        <div className="flex flex-col-reverse items-stretch gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:justify-end">
          <button type="submit" className="primary-button sm:min-w-40" disabled={!canSubmit}>
            <Send className="h-4 w-4" aria-hidden="true" />
            {createPO.isPending ? "Creating…" : "Create PO"}
          </button>
        </div>
      </form>
    </section>
  );
}

function ConsumptionPreview({
  category,
  fabricCode,
  perPiece,
  quantity,
  piecesFromStock,
  piecesToMake,
  piecesAvailableInStock,
  baseConsumption,
  wastageMeters,
  wastagePercent,
  totalConsumption,
  fabricOnHandMtrs,
  fabricShortageMtrs,
}: {
  category: ProductRead | undefined;
  fabricCode: string;
  perPiece: number;
  quantity: number;
  piecesFromStock: number;
  piecesToMake: number;
  piecesAvailableInStock: number;
  baseConsumption: number;
  wastageMeters: number;
  wastagePercent: number;
  totalConsumption: number;
  fabricOnHandMtrs: number;
  fabricShortageMtrs: number;
}) {
  const ready = category && fabricCode && quantity > 0;
  if (!ready) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">What this PO will need</p>
        <p className="mt-2 text-sm text-slate-500">Pick a category, fabric, and quantity to see fabric and stock impact.</p>
      </div>
    );
  }

  const allFromStock = piecesToMake === 0;

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Step 1 · Use what we have</p>
        <p className="mt-1 text-sm text-slate-700">
          {piecesAvailableInStock > 0 ? (
            <>
              <span className="font-semibold text-emerald-700">{formatNumber(piecesAvailableInStock)} pcs</span> of <span className="font-mono">{fabricCode}</span> are already in stock.
              {" "}We can ship <span className="font-semibold">{formatNumber(piecesFromStock)} pcs</span> straight from the warehouse.
            </>
          ) : (
            <>No <span className="font-mono">{fabricCode}</span> pieces in stock — everything must be made fresh.</>
          )}
        </p>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Step 2 · Make the remaining</p>
        {allFromStock ? (
          <p className="mt-1 text-sm font-semibold text-emerald-700">Nothing to make — stock covers the full order.</p>
        ) : (
          <dl className="mt-1 grid gap-3 text-sm sm:grid-cols-4">
            <Stat label="Pieces to make" value={formatNumber(piecesToMake)} />
            <Stat label="Per piece" value={`${perPiece.toFixed(2)} m`} />
            <Stat label="Base fabric" value={`${formatMeters(baseConsumption)} m`} sub={`${formatNumber(piecesToMake)} × ${perPiece.toFixed(2)}`} />
            <Stat label={`Wastage (${wastagePercent}%)`} value={`${formatMeters(wastageMeters)} m`} />
            <Stat label="Total fabric required" value={`${formatMeters(totalConsumption)} m`} highlight />
            <Stat label="Fabric on hand" value={`${formatMeters(fabricOnHandMtrs)} m`} />
            <Stat label="Fabric to order from mill" value={`${formatMeters(fabricShortageMtrs)} m`} tone={fabricShortageMtrs > 0 ? "alert" : "success"} />
          </dl>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, sub, highlight, tone }: { label: string; value: string; sub?: string; highlight?: boolean; tone?: "alert" | "success" }) {
  const cls =
    tone === "alert" ? "text-red-700"
    : tone === "success" ? "text-emerald-700"
    : highlight ? "text-teal-800"
    : "text-slate-950";
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className={`mt-0.5 truncate text-sm font-semibold tabular-nums ${cls}`}>{value}</dd>
      {sub ? <p className="text-[11px] text-slate-500">{sub}</p> : null}
    </div>
  );
}
