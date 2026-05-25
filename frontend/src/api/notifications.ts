import { api } from "./axios";
import type { UUID } from "../types/api";

export interface NotificationRead {
  id: UUID;
  user_id: UUID;
  purchase_order_id: UUID | null;
  notification_type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

export async function fetchNotifications(unread = false): Promise<NotificationRead[]> {
  const response = await api.get<NotificationRead[]>("/notifications", {
    params: { unread },
  });
  return response.data;
}

export async function markNotificationRead(id: UUID): Promise<NotificationRead | null> {
  const response = await api.post<NotificationRead | null>(`/notifications/${id}/read`);
  return response.data;
}
