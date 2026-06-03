import type { LucideIcon } from "lucide-react";
import { cn } from "../utils/cn";

type StatTone = "neutral" | "green" | "yellow" | "red" | "blue";

const toneClasses: Record<StatTone, { card: string; value: string; icon: string }> = {
  neutral: { card: "border-slate-200 bg-white",         value: "text-slate-950",    icon: "text-slate-400" },
  green:   { card: "border-emerald-200 bg-emerald-50",  value: "text-emerald-800",  icon: "text-emerald-600" },
  yellow:  { card: "border-amber-200 bg-amber-50",      value: "text-amber-900",    icon: "text-amber-600" },
  red:     { card: "border-red-200 bg-red-50",          value: "text-red-800",      icon: "text-red-600" },
  blue:    { card: "border-sky-200 bg-sky-50",          value: "text-sky-800",      icon: "text-sky-600" },
};

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  tone?: StatTone;
  active?: boolean;
  onClick?: () => void;
}

export function StatCard({ label, value, icon: Icon, tone = "neutral", active, onClick }: StatCardProps) {
  const t = toneClasses[tone];
  const className = cn(
    "rounded-lg border p-4 text-left transition",
    onClick ? "cursor-pointer hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-teal-500" : "",
    active ? "ring-2 ring-teal-600" : "",
    t.card,
  );
  const content = (
    <>
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-600">{label}</p>
        <Icon className={cn("h-4 w-4 shrink-0", t.icon)} aria-hidden="true" />
      </div>
      <p className={cn("mt-3 text-2xl font-bold tabular-nums", t.value)}>{value}</p>
    </>
  );
  if (onClick) {
    return (
      <button type="button" className={className} onClick={onClick} aria-pressed={active}>
        {content}
      </button>
    );
  }
  return (
    <section className={className}>
      {content}
    </section>
  );
}
