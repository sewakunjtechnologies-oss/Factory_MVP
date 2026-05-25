import { cn } from "../utils/cn";

interface ProgressBarProps {
  value: number;
  tone?: "green" | "yellow" | "red" | "blue";
}

const fillTone = {
  green: "bg-emerald-500",
  yellow: "bg-amber-500",
  red: "bg-red-500",
  blue: "bg-sky-500",
};

export function ProgressBar({ value, tone = "green" }: ProgressBarProps) {
  const filledSegments = Math.round(Math.max(0, Math.min(100, value)) / 5);
  return (
    <div className="grid h-2 w-full grid-cols-[repeat(20,minmax(0,1fr))] gap-0.5 overflow-hidden rounded-full" aria-label={`${value}% complete`}>
      {Array.from({ length: 20 }).map((_, index) => (
        <span
          key={index}
          className={cn("h-full min-w-0", index < filledSegments ? fillTone[tone] : "bg-slate-100")}
        />
      ))}
    </div>
  );
}
