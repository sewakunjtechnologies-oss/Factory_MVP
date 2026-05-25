import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { fetchNotifications, markNotificationRead, type NotificationRead } from "../api/notifications";
import type { UUID } from "../types/api";

const POLL_MS = 30_000;

export function useNotifications(unread = false) {
  return useQuery({
    queryKey: ["notifications", unread],
    queryFn: () => fetchNotifications(unread),
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => markNotificationRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

/**
 * Fires the supplied callback exactly once per newly-arriving notification.
 * Used by the toast layer to surface fresh notifications without re-toasting old ones.
 */
export function useNewNotificationCallback(
  notifications: NotificationRead[] | undefined,
  onNew: (notification: NotificationRead) => void,
) {
  const seenIdsRef = useRef<Set<string> | null>(null);
  const onNewRef = useRef(onNew);

  useEffect(() => {
    onNewRef.current = onNew;
  }, [onNew]);

  useEffect(() => {
    if (!notifications) return;
    if (seenIdsRef.current === null) {
      // First poll: prime the set, don't toast historical items.
      seenIdsRef.current = new Set(notifications.map((n) => n.id));
      return;
    }
    const seen = seenIdsRef.current;
    for (const notification of notifications) {
      if (!seen.has(notification.id)) {
        seen.add(notification.id);
        onNewRef.current(notification);
      }
    }
  }, [notifications]);
}
