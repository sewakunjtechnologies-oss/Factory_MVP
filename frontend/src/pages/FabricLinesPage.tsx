import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Download, Layers, Plus, Search } from "lucide-react";

import { api, resolveAssetUrl } from "../api/axios";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import {
  useProductFabricLines,
  useReceiveFabricMeters,
  useReceivePieces,
  useUpdateProductFabricLine,
} from "../hooks/useProductFabricLines";
import { useProducts } from "../hooks/usePurchaseOrders";
import type { ProductFabricLineRead, StageStatus, StockStatus } from "../api/productFabricLines";
import type { ProductRead, UUID } from "../types/api";
import { todayISO } from "../utils/forms";
import { formatMeters, formatNumber } from "../utils/format";

const STAGES = ["cutting", "stitching", "packing", "dispatch"] as const;
type Stage = (typeof STAGES)[number];

const STAGE_LABEL: Record<Stage, string> = {
  cutting: "Cutting",
  stitching: "Stitching",
  packing: "Packing",
  dispatch: "Dispatch",
};

function num(v: string | number | null | undefined): number {
  return v == null ? 0 : Number(v);
}

function fabricNeededRemaining(row: ProductFabricLineRead): number {
  // Pieces still to make = max(0, target - already in stock).
  const remaining = Math.max(0, row.pieces - row.pieces_in_stock);
  return remaining * num(row.per_piece_meters);
}

function fabricShortage(row: ProductFabricLineRead): number {
  return Math.max(0, fabricNeededRemaining(row) - num(row.stock_meters));
}

type NextStep = { stage: "Fabric" | "Cutting" | "Stitching" | "Packing" | "Dispatch" | "Complete"; action: string; urgent: boolean };

function nextStep(row: ProductFabricLineRead): NextStep {
  const short = fabricShortage(row);
  const remainingPieces = Math.max(0, row.pieces - row.pieces_in_stock);
  if (remainingPieces === 0 && row.pieces > 0) {
    return { stage: "Complete", action: "Stock target met", urgent: false };
  }
  if (row.dispatch === "done") return { stage: "Complete", action: "All stages complete", urgent: false };
  if (row.cutting !== "done" && short > 0) return { stage: "Fabric", action: `Order ${short.toLocaleString()} m more fabric`, urgent: true };
  if (row.cutting !== "done") return { stage: "Cutting", action: "Release to cutting", urgent: false };
  if (row.stitching !== "done") return { stage: "Stitching", action: "Send to stitching", urgent: false };
  if (row.packing !== "done") return { stage: "Packing", action: "Send to packing", urgent: false };
  return { stage: "Dispatch", action: "Ready for dispatch", urgent: false };
}

type StockDialogState = { open: boolean; preselected?: ProductFabricLineRead };

export default function FabricLinesPage() {
  const productsQuery = useProducts();
  const linesQuery = useProductFabricLines();
  const updateLine = useUpdateProductFabricLine();
  const receivePieces = useReceivePieces();
  const receiveFabric = useReceiveFabricMeters();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [stockDialog, setStockDialog] = useState<StockDialogState>({ open: false });

  const productsById = useMemo(() => {
    const map = new Map<UUID, ProductRead>();
    (productsQuery.data ?? []).forEach((p) => map.set(p.id, p));
    return map;
  }, [productsQuery.data]);

  const allLines = linesQuery.data ?? [];

  const filteredLines = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allLines.filter((line) => {
      const product = productsById.get(line.product_id);
      if (categoryFilter && product?.product_name !== categoryFilter) return false;
      if (!q) return true;
      return (
        line.fabric_code.toLowerCase().includes(q) ||
        (product?.product_name ?? "").toLowerCase().includes(q)
      );
    });
  }, [allLines, productsById, search, categoryFilter]);

  const categoryNames = useMemo(() => {
    const set = new Set<string>();
    allLines.forEach((line) => {
      const p = productsById.get(line.product_id);
      if (p?.product_name) set.add(p.product_name);
    });
    return Array.from(set).sort();
  }, [allLines, productsById]);

  const grouped = useMemo(() => {
    const groups = new Map<UUID, { product: ProductRead | undefined; lines: ProductFabricLineRead[] }>();
    filteredLines.forEach((line) => {
      const existing = groups.get(line.product_id);
      if (existing) {
        existing.lines.push(line);
      } else {
        groups.set(line.product_id, { product: productsById.get(line.product_id), lines: [line] });
      }
    });
    return Array.from(groups.values()).sort((a, b) =>
      (a.product?.product_name ?? "").localeCompare(b.product?.product_name ?? ""),
    );
  }, [filteredLines, productsById]);

  const globalTotals = useMemo(() => {
    return filteredLines.reduce(
      (acc, r) => {
        acc.target += r.pieces;
        acc.inStockPcs += r.pieces_in_stock;
        acc.remaining += Math.max(0, r.pieces - r.pieces_in_stock);
        acc.neededMtrs += fabricNeededRemaining(r);
        acc.fabricStockMtrs += num(r.stock_meters);
        acc.shortage += fabricShortage(r);
        return acc;
      },
      { target: 0, inStockPcs: 0, remaining: 0, neededMtrs: 0, fabricStockMtrs: 0, shortage: 0 },
    );
  }, [filteredLines]);

  if (productsQuery.isLoading || linesQuery.isLoading) return <LoadingState label="Loading fabric lines" />;
  if (allLines.length === 0) {
    return <EmptyState icon={Layers} title="No fabric lines yet" message="Create fabric variants for a category to start tracking stock." />;
  }

  function onStageChange(line: ProductFabricLineRead, stage: Stage, value: StageStatus) {
    updateLine.mutate({ id: line.id, payload: { [stage]: value } });
  }

  function triggerExcelExport() {
    const url = resolveAssetUrl("/api/v1/product-fabric-lines/export-xlsx");
    // The endpoint requires auth; opening it in a new tab carries the cookie/token
    // if the api instance has set one. Easiest path: stream via axios and trigger a Blob download.
    void api.get<Blob>("/product-fabric-lines/export-xlsx", { responseType: "blob" }).then((response) => {
      const contentType = typeof response.headers["content-type"] === "string" ? response.headers["content-type"] : undefined;
      const blob = new Blob([response.data], { type: contentType });
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = "fabric_inventory.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    }).catch(() => {
      // Fallback: navigate directly. If unauthorized, browser will show the API's 401.
      window.open(url, "_blank", "noopener");
    });
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-teal-700" aria-hidden="true" />
            <div>
              <h1 className="text-xl font-bold text-slate-950">Fabric &amp; Pieces Inventory</h1>
              <p className="text-sm text-slate-500">Stock target, finished pieces in warehouse, fabric on hand — across every category</p>
            </div>
          </div>
          <button
            type="button"
            className="primary-button shrink-0"
            onClick={() => setStockDialog({ open: true })}
            aria-label="Add a stock entry — pieces or fabric meters"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add stock entry
          </button>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_14rem_auto]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              className="field pl-9"
              placeholder="Search fabric or category"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search fabric lines"
            />
          </label>
          <select
            className="field"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            aria-label="Filter by category"
          >
            <option value="">All categories</option>
            {categoryNames.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <div className="flex flex-wrap gap-2 sm:justify-end">
            <button
              type="button"
              className="secondary-button"
              onClick={triggerExcelExport}
              aria-label="Download inventory as Excel"
              title="Download current inventory as an Excel file"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Download Excel</span>
              <span className="sm:hidden">Download</span>
            </button>
          </div>
        </div>

        <p className="mt-2 text-xs text-slate-500">
          Want to import an Excel file? Use <Link to="/ai-import" className="font-semibold text-teal-700 hover:underline">AI Excel import</Link> — it figures out the structure for you.
        </p>

        <div className="mt-5 grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Target pieces" value={formatNumber(globalTotals.target)} sub={`${filteredLines.length} fabric${filteredLines.length === 1 ? "" : "s"}`} />
          <StatCard label="In stock (pcs)" value={formatNumber(globalTotals.inStockPcs)} sub="finished, ready" tone="success" />
          <StatCard label="Still to make" value={formatNumber(globalTotals.remaining)} sub="pcs to produce" />
          <StatCard label="Fabric on hand" value={`${formatMeters(globalTotals.fabricStockMtrs)} m`} sub="ready for cutting" />
          <StatCard label="Fabric short" value={`${formatMeters(globalTotals.shortage)} m`} sub="to order from mill" tone={globalTotals.shortage > 0 ? "alert" : undefined} />
        </div>
      </section>

      {grouped.length === 0 ? (
        <EmptyState icon={Search} title="No matches" message="Adjust the search or category filter." />
      ) : (
        grouped.map(({ product, lines }) => (
          <ProductSection
            key={product?.id ?? "unknown"}
            product={product}
            lines={lines}
            onStageChange={onStageChange}
            onAddStock={(row) => setStockDialog({ open: true, preselected: row })}
            disabled={updateLine.isPending}
          />
        ))
      )}

      {updateLine.isError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          Failed to save: {(updateLine.error as Error)?.message ?? "Unknown error"}
        </div>
      ) : null}

      {stockDialog.open ? (
        <StockEntryDialog
          allLines={allLines}
          productsById={productsById}
          preselected={stockDialog.preselected}
          piecesBusy={receivePieces.isPending}
          metersBusy={receiveFabric.isPending}
          piecesError={receivePieces.error}
          metersError={receiveFabric.error}
          onClose={() => setStockDialog({ open: false })}
          onSubmit={async ({ lineId, pieces, meters, millName, notes }) => {
            // Run both receipts (whichever the owner filled in) in sequence so the
            // running counts on the line update before we close.
            if (meters && meters > 0) {
              await receiveFabric.mutateAsync({
                product_fabric_line_id: lineId,
                meters,
                mill_name: millName || null,
                notes: notes || null,
              });
            }
            if (pieces && pieces > 0) {
              await receivePieces.mutateAsync({
                product_fabric_line_id: lineId,
                pieces,
                mill_name: millName || null,
                notes: notes || null,
              });
            }
            setStockDialog({ open: false });
          }}
        />
      ) : null}
    </div>
  );
}

function ProductSection({
  product,
  lines,
  onStageChange,
  onAddStock,
  disabled,
}: {
  product: ProductRead | undefined;
  lines: ProductFabricLineRead[];
  onStageChange: (line: ProductFabricLineRead, stage: Stage, value: StageStatus) => void;
  onAddStock: (line: ProductFabricLineRead) => void;
  disabled?: boolean;
}) {
  const totals = useMemo(
    () =>
      lines.reduce(
        (acc, r) => {
          acc.target += r.pieces;
          acc.inStockPcs += r.pieces_in_stock;
          acc.remaining += Math.max(0, r.pieces - r.pieces_in_stock);
          acc.fabricStockMtrs += num(r.stock_meters);
          acc.neededMtrs += fabricNeededRemaining(r);
          acc.shortage += fabricShortage(r);
          return acc;
        },
        { target: 0, inStockPcs: 0, remaining: 0, fabricStockMtrs: 0, neededMtrs: 0, shortage: 0 },
      ),
    [lines],
  );

  const sortedLines = useMemo(() => [...lines].sort((a, b) => a.fabric_code.localeCompare(b.fabric_code)), [lines]);

  return (
    <section className="panel overflow-hidden">
      <header className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-slate-950">Category {product?.product_name ?? "—"}</h2>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
            {lines.length} fabric{lines.length === 1 ? "" : "s"}
          </span>
        </div>
        <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
          <SummaryStat label="Target" value={`${formatNumber(totals.target)} pcs`} />
          <SummaryStat label="In stock" value={`${formatNumber(totals.inStockPcs)} pcs`} tone="success" />
          <SummaryStat label="To make" value={`${formatNumber(totals.remaining)} pcs`} />
          <SummaryStat label="Fabric have" value={`${formatMeters(totals.fabricStockMtrs)} m`} />
          {totals.shortage > 0 ? <SummaryStat label="Fabric short" value={`${formatMeters(totals.shortage)} m`} tone="alert" /> : null}
        </dl>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="whitespace-nowrap px-3 py-3">Fabric</th>
              <th className="whitespace-nowrap px-3 py-3 text-right">Target pcs</th>
              <th className="whitespace-nowrap px-3 py-3 text-right">In stock</th>
              <th className="whitespace-nowrap px-3 py-3 text-right">To make</th>
              <th className="whitespace-nowrap px-3 py-3 text-right">m / pc</th>
              <th className="whitespace-nowrap px-3 py-3 text-right">Need (m)</th>
              <th className="whitespace-nowrap px-3 py-3 text-right">Have (m)</th>
              <th className="whitespace-nowrap px-3 py-3 text-right">Short (m)</th>
              {STAGES.map((s) => (
                <th key={s} className="whitespace-nowrap px-3 py-3 text-center">{STAGE_LABEL[s]}</th>
              ))}
              <th className="whitespace-nowrap px-3 py-3">Next step</th>
              <th className="whitespace-nowrap px-3 py-3 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sortedLines.map((row) => {
              const remaining = Math.max(0, row.pieces - row.pieces_in_stock);
              const need = fabricNeededRemaining(row);
              const short = fabricShortage(row);
              const step = nextStep(row);
              return (
                <tr key={row.id} className="align-middle">
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <span className="whitespace-nowrap font-semibold text-slate-950">{row.fabric_code}</span>
                      <StockStatusBadge status={row.stock_status} piecesShort={row.pieces_short} />
                    </div>
                  </td>
                  <td className="num-cell px-3 py-3 text-slate-700">{formatNumber(row.pieces)}</td>
                  <td className="num-cell px-3 py-3 font-semibold text-emerald-700">{formatNumber(row.pieces_in_stock)}</td>
                  <td className="num-cell px-3 py-3 text-slate-700">{formatNumber(remaining)}</td>
                  <td className="num-cell px-3 py-3 text-slate-500">{num(row.per_piece_meters).toFixed(2)}</td>
                  <td className="num-cell px-3 py-3 text-slate-700">{formatMeters(need)}</td>
                  <td className="num-cell px-3 py-3 text-slate-700">{formatMeters(num(row.stock_meters))}</td>
                  <td className={`num-cell px-3 py-3 ${short > 0 ? "font-semibold text-red-700" : "text-slate-300"}`}>
                    {short > 0 ? formatMeters(short) : "—"}
                  </td>
                  {STAGES.map((s) => (
                    <td key={s} className="px-3 py-3 text-center">
                      <StageSelect
                        value={row[s]}
                        disabled={disabled}
                        onChange={(value) => onStageChange(row, s, value)}
                        aria-label={`${STAGE_LABEL[s]} status for ${row.fabric_code}`}
                      />
                    </td>
                  ))}
                  <td className="px-3 py-3">
                    <NextStepPill step={step} />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <button
                      type="button"
                      className="chip-button"
                      onClick={() => onAddStock(row)}
                      aria-label={`Add stock for ${row.fabric_code}`}
                      title="Add pieces or fabric (meters) to stock"
                    >
                      <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                      Add stock
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SummaryStat({ label, value, tone }: { label: string; value: string; tone?: "alert" | "success" }) {
  const cls =
    tone === "alert" ? "text-red-700"
    : tone === "success" ? "text-emerald-700"
    : "text-slate-900";
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className={`text-xs font-semibold ${cls}`}>{value}</dd>
    </div>
  );
}

function NextStepPill({ step }: { step: { stage: string; action: string; urgent: boolean } }) {
  const tone =
    step.urgent ? "border-red-200 bg-red-50 text-red-700"
    : step.stage === "Complete" ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : "border-teal-200 bg-teal-50 text-teal-800";
  return (
    <div
      className={`inline-flex max-w-[18rem] items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-semibold ${tone}`}
      title={`${step.stage} — ${step.action}`}
    >
      <ArrowRight className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="shrink-0">{step.stage}</span>
      <span className="truncate font-normal opacity-90">— {step.action}</span>
    </div>
  );
}

type StockEntrySubmit = {
  lineId: UUID;
  pieces?: number;
  meters?: number;
  millName: string;
  notes: string;
};

function StockEntryDialog({
  allLines,
  productsById,
  preselected,
  piecesBusy,
  metersBusy,
  piecesError,
  metersError,
  onClose,
  onSubmit,
}: {
  allLines: ProductFabricLineRead[];
  productsById: Map<UUID, ProductRead>;
  preselected?: ProductFabricLineRead;
  piecesBusy: boolean;
  metersBusy: boolean;
  piecesError: unknown;
  metersError: unknown;
  onClose: () => void;
  onSubmit: (s: StockEntrySubmit) => Promise<void>;
}) {
  const [categoryId, setCategoryId] = useState<UUID | "">(preselected?.product_id ?? "");
  const [lineId, setLineId] = useState<UUID | "">(preselected?.id ?? "");
  const [pieces, setPieces] = useState("");
  const [meters, setMeters] = useState("");
  const [millName, setMillName] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // If the user changes the category, reset the fabric pick.
  useEffect(() => {
    if (preselected) return;
    if (!categoryId) return;
    // If current line doesn't belong to the new category, clear it.
    const line = allLines.find((l) => l.id === lineId);
    if (!line || line.product_id !== categoryId) setLineId("");
  }, [categoryId, lineId, allLines, preselected]);

  const categories = useMemo(() => {
    const set = new Map<UUID, ProductRead>();
    allLines.forEach((l) => {
      const p = productsById.get(l.product_id);
      if (p) set.set(p.id, p);
    });
    return Array.from(set.values()).sort((a, b) => a.product_name.localeCompare(b.product_name));
  }, [allLines, productsById]);

  const fabricChoices = useMemo(
    () => allLines.filter((l) => !categoryId || l.product_id === categoryId).sort((a, b) => a.fabric_code.localeCompare(b.fabric_code)),
    [allLines, categoryId],
  );

  const selectedLine = preselected ?? allLines.find((l) => l.id === lineId);
  const selectedCategory = selectedLine ? productsById.get(selectedLine.product_id) : undefined;

  const piecesNum = Math.max(0, Number(pieces) || 0);
  const metersNum = Math.max(0, Number(meters) || 0);
  const hasInput = piecesNum > 0 || metersNum > 0;
  const submitting = piecesBusy || metersBusy;
  const apiError = piecesError ?? metersError;

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    if (!selectedLine) {
      setFormError("Pick a category and fabric first.");
      return;
    }
    if (!hasInput) {
      setFormError("Enter pieces or meters (or both).");
      return;
    }
    void onSubmit({
      lineId: selectedLine.id,
      pieces: piecesNum > 0 ? piecesNum : undefined,
      meters: metersNum > 0 ? metersNum : undefined,
      millName: millName.trim(),
      notes: notes.trim(),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="stock-dialog-title">
      <div className="panel w-full max-w-lg p-5">
        <h3 id="stock-dialog-title" className="text-base font-bold text-slate-950">
          {preselected ? `Add stock — ${preselected.fabric_code}` : "Add stock entry"}
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          Log a receipt. Enter pieces, meters, or both — we'll update the running stock for you.
        </p>

        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          {preselected ? null : (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="label" htmlFor="stock-category">Category</label>
                <select
                  id="stock-category"
                  className="field"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value as UUID | "")}
                  required
                >
                  <option value="">Select category</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.product_name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="label" htmlFor="stock-fabric">Fabric</label>
                <select
                  id="stock-fabric"
                  className="field"
                  value={lineId}
                  onChange={(e) => setLineId(e.target.value as UUID | "")}
                  required
                  disabled={!categoryId && categories.length > 1}
                >
                  <option value="">Select fabric</option>
                  {fabricChoices.map((l) => (
                    <option key={l.id} value={l.id}>{l.fabric_code}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {selectedLine ? (
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
              <span className="font-semibold text-slate-900">{selectedCategory?.product_name} / {selectedLine.fabric_code}</span>
              {" — "}now: <span className="font-mono">{formatNumber(selectedLine.pieces_in_stock)} pcs</span>, <span className="font-mono">{formatMeters(num(selectedLine.stock_meters))} m</span>
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="label" htmlFor="stock-pieces">Finished pieces received</label>
              <input
                id="stock-pieces"
                type="number"
                min={0}
                step={1}
                inputMode="numeric"
                className="field"
                placeholder="e.g. 500"
                value={pieces}
                onChange={(e) => setPieces(e.target.value)}
                autoFocus={Boolean(preselected)}
              />
              <p className="text-[11px] text-slate-500">Adds to PC stock</p>
            </div>
            <div className="space-y-2">
              <label className="label" htmlFor="stock-meters">Fabric meters received</label>
              <input
                id="stock-meters"
                type="number"
                min={0}
                step="0.001"
                inputMode="decimal"
                className="field"
                placeholder="e.g. 1200"
                value={meters}
                onChange={(e) => setMeters(e.target.value)}
              />
              <p className="text-[11px] text-slate-500">Adds to fabric (meters) stock</p>
            </div>
          </div>

          <div className="space-y-2">
            <label className="label" htmlFor="stock-mill">From which mill / contractor? <span className="text-slate-400">(optional)</span></label>
            <input
              id="stock-mill"
              type="text"
              className="field"
              value={millName}
              onChange={(e) => setMillName(e.target.value)}
              placeholder="e.g. Krishna Mill"
              maxLength={150}
            />
          </div>
          <div className="space-y-2">
            <label className="label" htmlFor="stock-notes">Notes <span className="text-slate-400">(optional)</span></label>
            <textarea
              id="stock-notes"
              className="field min-h-16 py-2"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={2000}
            />
          </div>

          <p className="text-xs text-slate-500">Receipt date is today ({todayISO()}).</p>

          {formError ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</div>
          ) : null}
          {apiError ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {(apiError as Error)?.message ?? "Failed to save"}
            </div>
          ) : null}

          <div className="flex justify-end gap-2">
            <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary-button" disabled={submitting || !hasInput || !selectedLine}>
              {submitting ? "Saving…" : "Add to stock"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function StockStatusBadge({ status, piecesShort }: { status: StockStatus; piecesShort: number }) {
  const meta: Record<StockStatus, { label: string; cls: string; title: string }> = {
    extra:    { label: "Extra",    cls: "bg-emerald-100 text-emerald-800",   title: "Surplus stock — more than needed" },
    in_stock: { label: "In stock", cls: "bg-teal-100 text-teal-800",         title: "Pieces are in the warehouse" },
    ok:       { label: "OK",       cls: "bg-slate-100 text-slate-700",       title: "Stock is balanced — no action" },
    nil:      { label: "Nil",      cls: "bg-amber-100 text-amber-800",       title: "Zero in stock — need to make from scratch" },
    short:    { label: piecesShort > 0 ? `Short ${formatNumber(piecesShort)}` : "Short", cls: "bg-red-100 text-red-700", title: "We owe pieces — production needed" },
    unknown:  { label: "—",        cls: "bg-slate-50 text-slate-400 border border-dashed border-slate-200", title: "Status not set yet" },
  };
  const m = meta[status] ?? meta.unknown;
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${m.cls}`}
      title={m.title}
    >
      {m.label}
    </span>
  );
}

function StageSelect({
  value,
  disabled,
  onChange,
  ...rest
}: {
  value: StageStatus;
  disabled?: boolean;
  onChange: (v: StageStatus) => void;
  "aria-label"?: string;
}) {
  const toneClass =
    value === "done" ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
    : value === "in_progress" ? "border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100"
    : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100";
  return (
    <select
      {...rest}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as StageStatus)}
      className={`h-7 cursor-pointer rounded-md border pl-2 pr-1 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-teal-200 disabled:cursor-not-allowed disabled:opacity-60 ${toneClass}`}
    >
      <option value="pending">Pending</option>
      <option value="in_progress">WIP</option>
      <option value="done">Done</option>
    </select>
  );
}

function StatCard({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "alert" | "success" }) {
  const valueClass = tone === "alert" ? "text-red-700" : tone === "success" ? "text-emerald-700" : "text-slate-950";
  const borderClass = tone === "alert" ? "border-red-200 bg-red-50/40" : tone === "success" ? "border-emerald-200 bg-emerald-50/40" : "border-slate-200 bg-white";
  return (
    <div className={`rounded-lg border px-4 py-3 ${borderClass}`}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 truncate text-xl font-bold tabular-nums ${valueClass}`} title={value}>{value}</p>
      {sub ? <p className="mt-0.5 text-[11px] text-slate-500">{sub}</p> : null}
    </div>
  );
}
