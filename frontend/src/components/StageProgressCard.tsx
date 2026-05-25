import type { StageSummaryRead } from "../types/api";
import { getStageProgressPercent } from "../utils/factoryMetrics";
import { formatNumber, stageShortName } from "../utils/format";
import { ProgressBar } from "./ProgressBar";
import { StatusBadge } from "./StatusBadge";

export function StageProgressCard({ stage }: { stage: StageSummaryRead }) {
  const percent = getStageProgressPercent(stage);
  const tone = stage.rejected_qty > 0 ? "red" : stage.pending_qty > 0 ? "yellow" : "green";

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">{stageShortName(stage.stage)}</h3>
          <p className="mt-1 text-xs text-slate-500">{percent}% approved</p>
        </div>
        <StatusBadge value={stage.status} />
      </div>
      <div className="mt-4">
        <ProgressBar value={percent} tone={tone} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <Metric label="Completed" value={stage.completed_qty} />
        <Metric label="Approved" value={stage.approved_qty} />
        <Metric label="Rejected" value={stage.rejected_qty} danger />
        <Metric label="Pending" value={stage.pending_qty} warning={stage.pending_qty > 0} />
      </dl>
    </article>
  );
}

function Metric({ label, value, danger, warning }: { label: string; value: number; danger?: boolean; warning?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={danger ? "font-semibold text-red-700" : warning ? "font-semibold text-amber-700" : "font-semibold text-slate-950"}>
        {formatNumber(value)}
      </dd>
    </div>
  );
}
