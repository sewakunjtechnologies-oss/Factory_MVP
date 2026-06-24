import { Bell, CheckCircle2, Clock4 } from "lucide-react";

import { getApiErrorMessage } from "../../api/axios";
import { LoadingState } from "../../components/LoadingState";
import { useMarkMobileReminderHandled, useMobileReminders, useSnoozeMobileReminder } from "../../hooks/useMobileWorkflow";

export default function MobileAlertsPage() {
  const reminders = useMobileReminders();
  const snooze = useSnoozeMobileReminder();
  const handled = useMarkMobileReminderHandled();

  if (reminders.isLoading) return <LoadingState />;
  if (reminders.isError) return <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Could not load reminders.</div>;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-black text-slate-950">Alerts</h1>
        <p className="text-sm text-slate-500">Blocked and pending POs that need follow-up.</p>
      </header>
      {(snooze.isError || handled.isError) ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {getApiErrorMessage(snooze.error || handled.error)}
        </div>
      ) : null}
      <div className="space-y-3">
        {(reminders.data ?? []).map((reminder) => (
          <article key={reminder.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-50 text-amber-700">
                <Bell className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-bold text-slate-950">{reminder.title}</p>
                <p className="mt-1 text-sm text-slate-600">{reminder.message}</p>
                <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{reminder.priority} · due {reminder.due_date}</p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2">
              <button
                type="button"
                className="flex min-h-12 items-center justify-center gap-1 rounded-xl border border-slate-200 text-xs font-bold text-slate-700"
                onClick={() => snooze.mutate({ reminderId: reminder.id, payload: { hours: 4 } })}
              >
                <Clock4 className="h-4 w-4" /> 4 hrs
              </button>
              <button
                type="button"
                className="min-h-12 rounded-xl border border-slate-200 text-xs font-bold text-slate-700"
                onClick={() => {
                  const tomorrow = new Date();
                  tomorrow.setDate(tomorrow.getDate() + 1);
                  snooze.mutate({ reminderId: reminder.id, payload: { until_date: tomorrow.toISOString().slice(0, 10) } });
                }}
              >
                Tomorrow
              </button>
              <button
                type="button"
                className="flex min-h-12 items-center justify-center gap-1 rounded-xl bg-teal-700 text-xs font-bold text-white"
                onClick={() => handled.mutate(reminder.id)}
              >
                <CheckCircle2 className="h-4 w-4" /> Handled
              </button>
            </div>
          </article>
        ))}
        {(reminders.data ?? []).length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 text-center text-sm text-slate-500">No open reminders right now.</div>
        ) : null}
      </div>
    </div>
  );
}
