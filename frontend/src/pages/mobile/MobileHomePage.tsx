import { Bot, ClipboardPlus, ListChecks, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { MobilePOCard } from "../../components/mobile/MobilePOCard";
import { LoadingState } from "../../components/LoadingState";
import { useMobileHome, useMobileReminders } from "../../hooks/useMobileWorkflow";

export default function MobileHomePage() {
  const home = useMobileHome();
  const reminders = useMobileReminders();

  if (home.isLoading) return <LoadingState />;
  if (home.isError) return <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Could not load mobile dashboard.</div>;

  const data = home.data;

  return (
    <div className="space-y-4">
      <section className="rounded-3xl bg-slate-950 p-5 text-white shadow-sm">
        <p className="text-sm text-teal-100">Good day</p>
        <h1 className="mt-1 text-2xl font-black">Factory owner control</h1>
        <p className="mt-2 text-sm text-slate-300">Create POs, move stages, and see blocked work without long forms.</p>
      </section>

      <section className="grid grid-cols-2 gap-3">
        <Metric label="Active POs" value={data?.active_pos ?? 0} />
        <Metric label="Needs attention" value={data?.urgent_attention_count ?? 0} tone="amber" />
        <Metric label="Arrivals today" value={data?.expected_arrivals_today ?? 0} />
        <Metric label="Ready dispatch" value={data?.ready_for_dispatch_count ?? 0} tone="green" />
      </section>

      {reminders.data && reminders.data.length > 0 ? (
        <Link to="/mobile/alerts" className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
          <TriangleAlert className="h-5 w-5 shrink-0" />
          <div>
            <p className="font-bold">{reminders.data.length} POs need your attention</p>
            <p className="text-sm">{reminders.data[0].message}</p>
          </div>
        </Link>
      ) : null}

      <section className="grid grid-cols-2 gap-3">
        <QuickLink to="/mobile/po/create" icon={ClipboardPlus} label="Create PO" />
        <QuickLink to="/mobile/assistant" icon={Bot} label="Ask AI" />
        <QuickLink to="/mobile/pos" icon={ListChecks} label="Update Stage" />
        <QuickLink to="/mobile/alerts" icon={TriangleAlert} label="View Alerts" />
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-black text-slate-950">Current POs</h2>
          <Link to="/mobile/pos" className="text-sm font-bold text-teal-700">View all</Link>
        </div>
        {(data?.cards ?? []).slice(0, 8).map((po) => <MobilePOCard key={po.id} po={po} />)}
      </section>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: "amber" | "green" }) {
  const cls = tone === "amber" ? "text-amber-700" : tone === "green" ? "text-emerald-700" : "text-slate-950";
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className={`text-2xl font-black ${cls}`}>{value}</p>
      <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
    </div>
  );
}

function QuickLink({ to, icon: Icon, label }: { to: string; icon: typeof ClipboardPlus; label: string }) {
  return (
    <Link to={to} className="flex min-h-24 flex-col justify-between rounded-2xl border border-slate-200 bg-white p-4 font-bold text-slate-900 shadow-sm">
      <Icon className="h-6 w-6 text-teal-700" />
      <span>{label}</span>
    </Link>
  );
}
