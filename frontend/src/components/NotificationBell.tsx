import { Bell, Check } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useMarkNotificationRead, useNotifications } from "../hooks/useNotifications";

function formatRelative(iso: string): string {
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useNotifications();
  const markRead = useMarkNotificationRead();
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const unreadCount = useMemo(() => (data ?? []).filter((n) => !n.is_read).length, [data]);
  const recent = useMemo(() => (data ?? []).slice(0, 10), [data]);

  useEffect(() => {
    if (!open) return;
    function handleClick(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div className="relative" ref={wrapperRef}>
      <button
        type="button"
        className="relative rounded-md p-1 text-slate-500 hover:bg-slate-100"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
        onClick={() => setOpen((prev) => !prev)}
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-80 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg">
          <div className="border-b border-slate-200 px-4 py-2">
            <p className="text-sm font-semibold text-slate-950">Notifications</p>
            <p className="text-xs text-slate-500">{unreadCount} unread</p>
          </div>
          <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
            {isLoading ? (
              <div className="px-4 py-6 text-center text-sm text-slate-500">Loading…</div>
            ) : recent.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-slate-500">No notifications yet.</div>
            ) : (
              recent.map((notification) => (
                <div
                  key={notification.id}
                  className={`flex items-start gap-3 px-4 py-3 text-sm ${notification.is_read ? "bg-white" : "bg-amber-50"}`}
                >
                  <div className="flex-1">
                    <p className="font-semibold text-slate-950">{notification.title || notification.notification_type}</p>
                    <p className="mt-0.5 text-slate-600">{notification.message}</p>
                    <p className="mt-1 text-xs text-slate-400">{formatRelative(notification.created_at)}</p>
                  </div>
                  {!notification.is_read ? (
                    <button
                      type="button"
                      className="rounded p-1 text-teal-700 hover:bg-teal-50"
                      onClick={() => markRead.mutate(notification.id)}
                      title="Mark as read"
                      aria-label="Mark as read"
                    >
                      <Check className="h-4 w-4" />
                    </button>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
