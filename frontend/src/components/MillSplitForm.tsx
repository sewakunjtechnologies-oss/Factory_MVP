import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { getApiErrorMessage } from "../api/axios";
import { useCreateMillOrderSplit } from "../hooks/useOperations";
import type { MillSplitItem, UUID } from "../types/api";
import { todayISO } from "../utils/forms";

interface MillSplitFormProps {
  purchaseOrderId: UUID;
  shortageMeters?: number;
}

interface SplitRow extends MillSplitItem {
  rowId: string;
}

function newRow(): SplitRow {
  return {
    rowId: Math.random().toString(36).slice(2),
    mill_name: "",
    split_percent: 0,
    committed_delivery_date: todayISO(),
  };
}

export function MillSplitForm({ purchaseOrderId, shortageMeters }: MillSplitFormProps) {
  const [rows, setRows] = useState<SplitRow[]>([newRow(), newRow()]);
  const createSplit = useCreateMillOrderSplit();

  const totalPercent = rows.reduce((sum, row) => sum + (Number(row.split_percent) || 0), 0);
  const valid = rows.every((row) => row.mill_name.trim() && row.split_percent > 0 && row.committed_delivery_date) && totalPercent === 100;

  function updateRow(rowId: string, patch: Partial<SplitRow>) {
    setRows((current) => current.map((row) => (row.rowId === rowId ? { ...row, ...patch } : row)));
  }

  function removeRow(rowId: string) {
    setRows((current) => (current.length > 1 ? current.filter((row) => row.rowId !== rowId) : current));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid) return;
    createSplit.mutate(
      {
        purchase_order_id: purchaseOrderId,
        splits: rows.map(({ rowId: _rowId, ...split }) => ({
          ...split,
          split_percent: Number(split.split_percent),
          ordered_width: split.ordered_width ? Number(split.ordered_width) : null,
          ordered_gsm: split.ordered_gsm ? Number(split.ordered_gsm) : null,
          ordered_rate_per_meter: split.ordered_rate_per_meter ? Number(split.ordered_rate_per_meter) : null,
        })),
      },
      {
        onSuccess: () => setRows([newRow(), newRow()]),
      },
    );
  }

  return (
    <form className="panel p-4" onSubmit={submit}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">Split Mill Order</h2>
          <p className="text-xs text-slate-500">
            Split the shortage across multiple mills by percentage (e.g., 30% / 70%).
            {shortageMeters ? <> Total shortage: <strong>{shortageMeters.toLocaleString()} m</strong>.</> : null}
          </p>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={() => setRows((current) => [...current, newRow()])}
          aria-label="Add mill"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-3 space-y-3">
        {rows.map((row) => {
          const allocatedMeters =
            shortageMeters && row.split_percent ? (shortageMeters * Number(row.split_percent)) / 100 : 0;
          return (
            <div key={row.rowId} className="rounded-md border border-slate-200 p-3">
              <div className="grid gap-2 sm:grid-cols-3">
                <input
                  className="field"
                  placeholder="Mill name"
                  value={row.mill_name}
                  onChange={(event) => updateRow(row.rowId, { mill_name: event.target.value })}
                  required
                />
                <input
                  className="field"
                  type="number"
                  min={0}
                  max={100}
                  step={0.01}
                  placeholder="Split %"
                  value={row.split_percent || ""}
                  onChange={(event) => updateRow(row.rowId, { split_percent: Number(event.target.value) })}
                  required
                />
                <input
                  className="field"
                  type="date"
                  value={row.committed_delivery_date}
                  onChange={(event) => updateRow(row.rowId, { committed_delivery_date: event.target.value })}
                  required
                />
                <input
                  className="field"
                  type="number"
                  min={0}
                  step={0.01}
                  placeholder="Rate / m (optional)"
                  value={row.ordered_rate_per_meter ?? ""}
                  onChange={(event) =>
                    updateRow(row.rowId, { ordered_rate_per_meter: event.target.value ? Number(event.target.value) : null })
                  }
                />
                <input
                  className="field"
                  type="number"
                  min={0}
                  step={0.1}
                  placeholder="Width (optional)"
                  value={row.ordered_width ?? ""}
                  onChange={(event) =>
                    updateRow(row.rowId, { ordered_width: event.target.value ? Number(event.target.value) : null })
                  }
                />
                <input
                  className="field"
                  type="number"
                  min={0}
                  step={0.1}
                  placeholder="GSM (optional)"
                  value={row.ordered_gsm ?? ""}
                  onChange={(event) =>
                    updateRow(row.rowId, { ordered_gsm: event.target.value ? Number(event.target.value) : null })
                  }
                />
              </div>
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                {allocatedMeters > 0 ? (
                  <span>→ approx <strong>{Math.round(allocatedMeters).toLocaleString()} m</strong> to {row.mill_name || "mill"}</span>
                ) : (
                  <span />
                )}
                {rows.length > 1 ? (
                  <button
                    type="button"
                    className="text-red-700 hover:text-red-900"
                    onClick={() => removeRow(row.rowId)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex items-center justify-between text-sm">
        <span className={totalPercent === 100 ? "text-emerald-700" : "text-amber-700"}>
          Total: <strong>{totalPercent.toFixed(2)}%</strong> {totalPercent === 100 ? "✓" : "(must equal 100)"}
        </span>
        <button className="primary-button" disabled={!valid || createSplit.isPending} type="submit">
          {createSplit.isPending ? "Creating…" : "Create Split"}
        </button>
      </div>

      {createSplit.isError ? (
        <p className="mt-2 text-sm text-red-700">{getApiErrorMessage(createSplit.error)}</p>
      ) : null}
      {createSplit.isSuccess ? (
        <p className="mt-2 text-sm text-emerald-700">Mill orders created from split.</p>
      ) : null}
    </form>
  );
}
