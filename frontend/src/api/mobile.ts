import { api } from "./axios";
import type { UUID } from "../types/api";

export interface MobileCategoryOption {
  id: UUID;
  product_id: UUID;
  category_name: string;
  fabric_code: string;
  searchable_text: string;
  per_piece_meters: string;
  stock_meters: string;
  pieces_in_stock: number;
}

export interface MobilePOCreate {
  category_option_id: UUID;
  quantity: number;
  delivery_mode: "month" | "date";
  delivery_month?: string | null;
  delivery_date?: string | null;
}

export interface MobilePOCard {
  id: UUID;
  po_number: string;
  category_name: string;
  fabric_code: string | null;
  quantity: number;
  delivery_date: string;
  delivery_label: string;
  current_stage: string;
  status: string;
  warning: string | null;
  is_historical: boolean;
  next_action_label: string;
  required_fabric_m: string | null;
  available_fabric_m: string | null;
  shortage_m: string | null;
}

export interface MobileHomeSummary {
  active_pos: number;
  urgent_attention_count: number;
  expected_arrivals_today: number;
  ready_for_dispatch_count: number;
  cards: MobilePOCard[];
}

export interface MobileTransitionPreview {
  po_id: UUID;
  po_number: string;
  current_stage: string;
  next_stage: string;
  action_label: string;
  required_fields: Array<{ name: string; label: string; type: string; required: boolean; default?: unknown }>;
  can_execute: boolean;
  message: string;
}

export interface MobileTransitionRequest {
  action?: string | null;
  values: Record<string, unknown>;
  confirm: boolean;
}

export interface MobileTransitionResult {
  success: boolean;
  message: string;
  card: MobilePOCard | null;
  preview: MobileTransitionPreview | null;
}

export interface MobileReminder {
  id: string;
  title: string;
  message: string;
  due_date: string;
  priority: string;
  purchase_order_id: string;
}

export async function fetchMobileHome(): Promise<MobileHomeSummary> {
  const response = await api.get<MobileHomeSummary>("/mobile/home");
  return response.data;
}

export async function fetchMobilePOs(): Promise<MobilePOCard[]> {
  const response = await api.get<MobilePOCard[]>("/mobile/pos");
  return response.data;
}

export async function fetchMobileCategoryOptions(): Promise<MobileCategoryOption[]> {
  const response = await api.get<MobileCategoryOption[]>("/mobile/category-options");
  return response.data;
}

export async function createMobilePO(payload: MobilePOCreate): Promise<MobilePOCard> {
  const response = await api.post<MobilePOCard>("/mobile/pos", payload);
  return response.data;
}

export async function fetchMobileTransitionPreview(poId: UUID): Promise<MobileTransitionPreview> {
  const response = await api.get<MobileTransitionPreview>(`/mobile/pos/${poId}/transition`);
  return response.data;
}

export async function executeMobileTransition(poId: UUID, payload: MobileTransitionRequest): Promise<MobileTransitionResult> {
  const response = await api.post<MobileTransitionResult>(`/mobile/pos/${poId}/transition`, payload);
  return response.data;
}

export async function fetchMobileReminders(): Promise<MobileReminder[]> {
  const response = await api.get<MobileReminder[]>("/mobile/reminders/summary");
  return response.data;
}

export async function snoozeMobileReminder(reminderId: string, payload: { hours?: number; until_date?: string | null }): Promise<{ message: string }> {
  const response = await api.post<{ message: string }>(`/mobile/reminders/${reminderId}/snooze`, payload);
  return response.data;
}

export async function markMobileReminderHandled(reminderId: string): Promise<{ message: string }> {
  const response = await api.post<{ message: string }>(`/mobile/reminders/${reminderId}/handled`);
  return response.data;
}
