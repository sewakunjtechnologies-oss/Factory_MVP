import { AlertTriangle, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import type { MobilePOCard as MobilePOCardData } from "../../api/mobile";
import { formatNumber } from "../../utils/format";

export function MobilePOCard({ po }: { po: MobilePOCardData }) {
  return (
    <Link to={`/mobile/po/${po.id}`} className="block rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-xs font-semibold uppercase tracking-wide text-teal-700">{po.po_number}</p>
          <h2 className="mt-1 line-clamp-2 text-base font-bold text-slate-950">{po.fabric_code || po.category_name}</h2>
          <p className="mt-1 text-sm text-slate-500">{formatNumber(po.quantity)} pcs · {po.delivery_label}</p>
        </div>
        <ChevronRight className="mt-1 h-5 w-5 shrink-0 text-slate-400" />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">{po.current_stage.replaceAll("_", " ")}</span>
        {po.is_historical ? <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">Historical Import</span> : null}
      </div>
      {po.warning ? (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{po.warning}</span>
        </div>
      ) : null}
      <div className="mt-3 rounded-xl bg-teal-50 px-3 py-2 text-sm font-bold text-teal-800">{po.next_action_label}</div>
    </Link>
  );
}
