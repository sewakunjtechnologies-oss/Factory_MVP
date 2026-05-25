export function LoadingState({ label = "Loading factory data" }: { label?: string }) {
  return (
    <div className="panel flex min-h-40 items-center justify-center">
      <div className="flex items-center gap-3 text-sm font-medium text-slate-600">
        <span className="h-3 w-3 animate-pulse rounded-full bg-teal-600" />
        {label}
      </div>
    </div>
  );
}
