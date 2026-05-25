import { type ChangeEvent, type DragEvent, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  RotateCcw,
  Sparkles,
  Upload,
} from "lucide-react";

import { api, getApiErrorMessage } from "../api/axios";

type AnalyzeResponse = {
  plan: {
    target_table: "product_fabric_lines" | "pieces_receipts" | "fabric_meter_receipts";
    column_mapping: Record<string, string>;
    match_columns: Record<string, string>;
    action: "upsert" | "insert" | "update_only";
    confidence: number;
    reasoning: string;
    warnings: string[];
  };
  table_info: {
    description: string;
    match_key: string[];
    writable_columns: Record<string, string>;
    action: string;
  };
  sample: {
    sheet: string;
    headers: string[];
    first_rows: (string | number | boolean | null)[][];
    approx_total_rows: number;
  };
};

type CommitResponse = {
  target_table: string;
  applied: number;
  skipped: { row: number; reason: string }[];
  changes: Array<{ row: number; category: string; fabric_code: string } & Record<string, unknown>>;
};

const TARGET_LABELS: Record<AnalyzeResponse["plan"]["target_table"], string> = {
  product_fabric_lines: "Fabric & pieces inventory (update existing rows)",
  pieces_receipts: "Pieces receipts (log new receipt events)",
  fabric_meter_receipts: "Fabric meter receipts (log new fabric arrivals)",
};

export default function AiImportPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [commitResult, setCommitResult] = useState<CommitResponse | null>(null);
  const [busy, setBusy] = useState<"" | "analyzing" | "committing">("");
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setFile(null);
    setAnalysis(null);
    setCommitResult(null);
    setError(null);
    setBusy("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function pickFile(next: File | null) {
    setAnalysis(null);
    setCommitResult(null);
    setError(null);
    setFile(next);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0] ?? null;
    if (dropped) pickFile(dropped);
  }

  async function runAnalyze() {
    if (!file) return;
    setBusy("analyzing");
    setError(null);
    setAnalysis(null);
    setCommitResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await api.post<AnalyzeResponse>("/ai-import/analyze", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setAnalysis(response.data);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setBusy("");
    }
  }

  async function runCommit() {
    if (!file || !analysis) return;
    setBusy("committing");
    setError(null);
    setCommitResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("plan_json", JSON.stringify(analysis.plan));
      const response = await api.post<CommitResponse>("/ai-import/commit", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setCommitResult(response.data);
      // Invalidate inventory caches so the inventory page reflects the new state.
      await queryClient.invalidateQueries({ queryKey: ["product-fabric-lines"] });
      await queryClient.invalidateQueries({ queryKey: ["pieces-receipts"] });
      await queryClient.invalidateQueries({ queryKey: ["fabric-meter-receipts"] });
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setBusy("");
    }
  }

  const confidencePct = analysis ? Math.round((analysis.plan.confidence ?? 0) * 100) : 0;
  const confidenceTone =
    confidencePct >= 80 ? "text-emerald-700" : confidencePct >= 50 ? "text-amber-700" : "text-red-700";

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <header className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-teal-50 text-teal-700">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-slate-950">AI Excel import</h1>
            <p className="mt-0.5 text-sm text-slate-500">
              Upload any Excel file — Gemini reads the headers, figures out which table it belongs to,
              and shows you exactly what will change before you apply it.
            </p>
          </div>
        </header>

        <div className="mt-5">
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="sr-only"
            onChange={(e: ChangeEvent<HTMLInputElement>) => pickFile(e.target.files?.[0] ?? null)}
          />
          <label
            htmlFor=""
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
              dragging ? "border-teal-400 bg-teal-50/60" : "border-slate-300 bg-slate-50 hover:border-teal-300 hover:bg-teal-50/40"
            }`}
          >
            <Upload className="h-7 w-7 text-slate-400" aria-hidden="true" />
            {file ? (
              <div className="space-y-1">
                <p className="text-sm font-semibold text-slate-900">{file.name}</p>
                <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB · ready to analyze</p>
              </div>
            ) : (
              <div className="space-y-1">
                <p className="text-sm font-semibold text-slate-700">Drop an Excel file here, or click to pick one</p>
                <p className="text-xs text-slate-500">.xlsx only · max 5 MB</p>
              </div>
            )}
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="primary-button"
            onClick={runAnalyze}
            disabled={!file || busy !== ""}
          >
            {busy === "analyzing" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Analyzing…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                Analyze with AI
              </>
            )}
          </button>
          <button type="button" className="secondary-button" onClick={reset} disabled={!file && !analysis}>
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Start over
          </button>
        </div>

        {error ? (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            <AlertTriangle className="mr-2 inline h-4 w-4 align-text-bottom" aria-hidden="true" />
            {error}
          </div>
        ) : null}
      </section>

      {analysis ? (
        <section className="panel overflow-hidden">
          <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="text-sm font-bold text-slate-950">AI plan</h2>
              <p className="mt-0.5 text-xs text-slate-500">Review carefully before committing.</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Confidence</p>
              <p className={`text-lg font-bold tabular-nums ${confidenceTone}`}>{confidencePct}%</p>
            </div>
          </header>

          <div className="space-y-4 px-5 py-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Target table</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-900">{TARGET_LABELS[analysis.plan.target_table]}</p>
              <p className="mt-1 text-xs text-slate-500">{analysis.table_info.description}</p>
            </div>

            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Reasoning</p>
              <p className="mt-0.5 text-sm text-slate-700">{analysis.plan.reasoning || "—"}</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <MappingPanel
                title="Matching key (used to find the row)"
                emptyMessage="AI did not identify which Excel columns hold the matching keys."
                mapping={analysis.plan.match_columns}
              />
              <MappingPanel
                title="Field mapping"
                emptyMessage="AI did not map any writable fields."
                mapping={analysis.plan.column_mapping}
              />
            </div>

            {analysis.plan.warnings.length > 0 ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <p className="font-semibold">Warnings from the AI</p>
                <ul className="mt-1 list-disc pl-5 text-xs">
                  {analysis.plan.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            ) : null}

            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Excel preview · sheet "{analysis.sample.sheet}" · {analysis.sample.approx_total_rows} data row{analysis.sample.approx_total_rows === 1 ? "" : "s"}
              </p>
              <div className="mt-2 overflow-x-auto rounded-md border border-slate-200">
                <table className="min-w-full text-xs">
                  <thead className="bg-slate-50 text-left font-semibold text-slate-600">
                    <tr>
                      <th className="px-2 py-1.5 text-right text-slate-400">#</th>
                      {analysis.sample.headers.map((h, i) => (
                        <th key={i} className="whitespace-nowrap px-2 py-1.5">{h || <span className="text-slate-400">(blank)</span>}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {analysis.sample.first_rows.map((row, i) => (
                      <tr key={i}>
                        <td className="px-2 py-1.5 text-right font-mono text-slate-400">{i + 2}</td>
                        {analysis.sample.headers.map((_, j) => (
                          <td key={j} className="whitespace-nowrap px-2 py-1.5 font-mono text-slate-700">
                            {row[j] === null || row[j] === undefined || row[j] === "" ? <span className="text-slate-300">—</span> : String(row[j])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {analysis.sample.approx_total_rows > analysis.sample.first_rows.length ? (
                <p className="mt-1 text-[11px] text-slate-500">Showing first {analysis.sample.first_rows.length} of {analysis.sample.approx_total_rows} rows.</p>
              ) : null}
            </div>
          </div>

          <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3">
            <p className="text-xs text-slate-600">
              {confidencePct < 50 ? (
                <span className="text-red-700">Low confidence — double-check before applying.</span>
              ) : confidencePct < 80 ? (
                <span className="text-amber-700">Moderate confidence — review the mapping above.</span>
              ) : (
                <span className="text-emerald-700">High confidence — looks safe to apply.</span>
              )}
            </p>
            <button
              type="button"
              className="primary-button"
              onClick={runCommit}
              disabled={busy !== "" || !analysis}
            >
              {busy === "committing" ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Applying…
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  Apply to database
                </>
              )}
            </button>
          </footer>
        </section>
      ) : null}

      {commitResult ? (
        <section className="panel overflow-hidden border-emerald-200 bg-emerald-50/40">
          <header className="border-b border-emerald-200 px-5 py-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-emerald-700" aria-hidden="true" />
              <h2 className="text-sm font-bold text-emerald-900">
                Imported into <span className="font-mono">{commitResult.target_table}</span>
              </h2>
            </div>
            <p className="mt-1 text-xs text-emerald-800">
              {commitResult.applied} row{commitResult.applied === 1 ? "" : "s"} applied
              {commitResult.skipped.length > 0 ? `, ${commitResult.skipped.length} skipped` : ""}.
            </p>
          </header>

          {commitResult.skipped.length > 0 ? (
            <div className="border-b border-emerald-200/60 bg-amber-50 px-5 py-3 text-sm">
              <p className="font-semibold text-amber-900">
                <FileSpreadsheet className="mr-1 inline h-4 w-4 align-text-bottom" aria-hidden="true" />
                Skipped rows
              </p>
              <ul className="mt-1 list-disc pl-5 text-xs text-amber-900">
                {commitResult.skipped.slice(0, 30).map((s, i) => (
                  <li key={i}>Row {s.row}: {s.reason}</li>
                ))}
                {commitResult.skipped.length > 30 ? <li>… and {commitResult.skipped.length - 30} more.</li> : null}
              </ul>
            </div>
          ) : null}

          {commitResult.changes.length > 0 ? (
            <div className="px-5 py-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                Applied changes (first {Math.min(commitResult.changes.length, 30)})
              </p>
              <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
                <table className="min-w-full text-xs">
                  <thead className="bg-slate-50 text-left font-semibold text-slate-600">
                    <tr>
                      <th className="px-2 py-1.5 text-right">Row</th>
                      <th className="px-2 py-1.5">Category</th>
                      <th className="px-2 py-1.5">Fabric</th>
                      <th className="px-2 py-1.5">Change</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {commitResult.changes.slice(0, 30).map((c, i) => (
                      <tr key={i}>
                        <td className="px-2 py-1.5 text-right font-mono text-slate-500">{c.row}</td>
                        <td className="whitespace-nowrap px-2 py-1.5 font-semibold text-slate-900">{c.category}</td>
                        <td className="whitespace-nowrap px-2 py-1.5 font-mono">{c.fabric_code}</td>
                        <td className="px-2 py-1.5 font-mono text-slate-700">{formatChange(c)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function MappingPanel({
  title,
  emptyMessage,
  mapping,
}: {
  title: string;
  emptyMessage: string;
  mapping: Record<string, string>;
}) {
  const entries = Object.entries(mapping).filter(([, v]) => v);
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{title}</p>
      {entries.length === 0 ? (
        <p className="mt-1 text-xs text-slate-400">{emptyMessage}</p>
      ) : (
        <dl className="mt-2 space-y-1">
          {entries.map(([db, excel]) => (
            <div key={db} className="flex items-center justify-between gap-2 text-xs">
              <dt className="font-mono text-slate-700">{db}</dt>
              <dd className="truncate text-right text-slate-500">← <span className="font-mono">{excel}</span></dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function formatChange(c: Record<string, unknown>): string {
  if (c.fields && typeof c.fields === "object") {
    return Object.entries(c.fields as Record<string, { from: unknown; to: unknown }>)
      .map(([k, v]) => `${k}: ${formatVal(v.from)} → ${formatVal(v.to)}`)
      .join(", ") || "—";
  }
  if (c.inserted) return `insert ${c.inserted} (${c.pieces ?? c.meters ?? ""})`;
  return "—";
}
function formatVal(v: unknown): string {
  if (v === null || v === undefined) return "∅";
  return String(v);
}
