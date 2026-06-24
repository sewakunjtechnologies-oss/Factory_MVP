import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { MobilePOCard } from "../../components/mobile/MobilePOCard";
import { LoadingState } from "../../components/LoadingState";
import { useMobilePOs } from "../../hooks/useMobileWorkflow";

export default function MobilePOListPage() {
  const [query, setQuery] = useState("");
  const pos = useMobilePOs();
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return pos.data ?? [];
    return (pos.data ?? []).filter((po) =>
      [po.po_number, po.category_name, po.fabric_code, po.current_stage, po.delivery_label]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q)),
    );
  }, [pos.data, query]);

  if (pos.isLoading) return <LoadingState />;
  if (pos.isError) return <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Could not load POs.</div>;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-black text-slate-950">Purchase orders</h1>
        <p className="text-sm text-slate-500">Tap a PO to update its stage.</p>
      </header>
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
        <input
          className="field h-14 rounded-2xl pl-12 text-base"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search PO, category, stage"
        />
      </div>
      <div className="space-y-3">
        {filtered.map((po) => <MobilePOCard key={po.id} po={po} />)}
        {filtered.length === 0 ? <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">No matching POs found.</div> : null}
      </div>
    </div>
  );
}
