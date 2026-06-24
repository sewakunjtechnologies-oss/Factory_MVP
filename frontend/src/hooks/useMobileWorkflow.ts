import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createMobilePO,
  executeMobileTransition,
  fetchMobileCategoryOptions,
  fetchMobileHome,
  fetchMobilePOs,
  fetchMobileReminders,
  fetchMobileTransitionPreview,
  markMobileReminderHandled,
  snoozeMobileReminder,
  type MobilePOCreate,
  type MobileTransitionRequest,
} from "../api/mobile";
import type { UUID } from "../types/api";

export function useMobileHome() {
  return useQuery({ queryKey: ["mobile-home"], queryFn: fetchMobileHome, staleTime: 20_000 });
}

export function useMobilePOs() {
  return useQuery({ queryKey: ["mobile-pos"], queryFn: fetchMobilePOs, staleTime: 20_000 });
}

export function useMobileCategoryOptions() {
  return useQuery({ queryKey: ["mobile-category-options"], queryFn: fetchMobileCategoryOptions, staleTime: 60_000 });
}

export function useCreateMobilePO() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: MobilePOCreate) => createMobilePO(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["mobile-home"] });
      void qc.invalidateQueries({ queryKey: ["mobile-pos"] });
      void qc.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
  });
}

export function useMobileTransitionPreview(poId?: UUID) {
  return useQuery({
    queryKey: ["mobile-transition-preview", poId],
    queryFn: () => fetchMobileTransitionPreview(poId as UUID),
    enabled: Boolean(poId),
  });
}

export function useExecuteMobileTransition(poId: UUID) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: MobileTransitionRequest) => executeMobileTransition(poId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["mobile-home"] });
      void qc.invalidateQueries({ queryKey: ["mobile-pos"] });
      void qc.invalidateQueries({ queryKey: ["mobile-transition-preview", poId] });
      void qc.invalidateQueries({ queryKey: ["purchase-order", poId] });
    },
  });
}

export function useMobileReminders() {
  return useQuery({ queryKey: ["mobile-reminders"], queryFn: fetchMobileReminders, staleTime: 20_000, refetchInterval: 4 * 60 * 60 * 1000 });
}

export function useSnoozeMobileReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ reminderId, payload }: { reminderId: string; payload: { hours?: number; until_date?: string | null } }) => snoozeMobileReminder(reminderId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["mobile-reminders"] });
      void qc.invalidateQueries({ queryKey: ["mobile-home"] });
    },
  });
}

export function useMarkMobileReminderHandled() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reminderId: string) => markMobileReminderHandled(reminderId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["mobile-reminders"] });
      void qc.invalidateQueries({ queryKey: ["mobile-home"] });
    },
  });
}
