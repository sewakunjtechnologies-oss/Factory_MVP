import { X } from "lucide-react";
import { useCallback, useState } from "react";

import { useNewNotificationCallback, useNotifications } from "../hooks/useNotifications";
import type { NotificationRead } from "../api/notifications";

interface ActiveToast {
  id: string;
  title: string;
  message: string;
}

const AUTO_DISMISS_MS = 6000;

export function NotificationToaster() {
  const { data } = useNotifications();
  const [toasts, setToasts] = useState<ActiveToast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const handleNew = useCallback(
    (notification: NotificationRead) => {
      const toast: ActiveToast = {
        id: notification.id,
        title: notification.title || notification.notification_type,
        message: notification.message,
      };
      setToasts((current) => [...current, toast]);
      window.setTimeout(() => removeToast(toast.id), AUTO_DISMISS_MS);
    },
    [removeToast],
  );

  useNewNotificationCallback(data, handleNew);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex max-w-sm flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="pointer-events-auto flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-lg"
          role="status"
          aria-live="polite"
        >
          <div className="flex-1">
            <p className="font-semibold">{toast.title}</p>
            <p className="mt-0.5 text-amber-800">{toast.message}</p>
          </div>
          <button
            type="button"
            onClick={() => removeToast(toast.id)}
            className="rounded p-0.5 text-amber-700 hover:bg-amber-100"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
