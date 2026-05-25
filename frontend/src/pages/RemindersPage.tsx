import { CheckCircle2 } from "lucide-react";

import { useCompleteReminder, useDueReminders } from "../hooks/useOperations";
import { formatDate } from "../utils/format";

export default function RemindersPage() {
  const reminders = useDueReminders();
  const complete = useCompleteReminder();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-950">Reminders</h1>
        <p className="mt-1 text-sm text-slate-500">Task follow-up reminders are separate from risk alerts.</p>
      </div>

      <section className="panel overflow-hidden">
        <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-950">Due Today / Overdue</div>
        <div className="divide-y divide-slate-100">
          {(reminders.data ?? []).map((item) => (
            <div key={item.id} className="grid items-center gap-3 px-4 py-3 sm:grid-cols-[1fr_auto]">
              <div>
                <p className="font-semibold text-slate-900">{item.title}</p>
                <p className="text-xs text-slate-500">{item.reminder_type} · Due {formatDate(item.due_date)}</p>
                <p className="mt-1 text-sm text-slate-600">{item.message}</p>
              </div>
              <button className="secondary-button" disabled={complete.isPending} onClick={() => complete.mutate(item.id)}>
                <CheckCircle2 className="h-4 w-4" />Complete
              </button>
            </div>
          ))}
          {(reminders.data ?? []).length === 0 ? <div className="px-4 py-8 text-sm text-slate-500">No due reminders.</div> : null}
        </div>
      </section>
    </div>
  );
}
