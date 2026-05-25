import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  completeReminder,
  createCapacityProfile,
  createCuttingAnalysis,
  createFabricMillOrder,
  createMillFollowup,
  createMillOrderSplit,
  fetchCapacityForecast,
  fetchCapacityProfiles,
  fetchCuttingAnalysis,
  fetchDueReminders,
  fetchFabricIssues,
  fetchFabricMillOrders,
  fetchLateMillOrders,
  fetchMillFollowupsDue,
  fetchMillOrderSplits,
  fetchMillWastageHistory,
  fetchMillWastageRecords,
  fetchReminders,
  fetchUnderutilization,
  issueFabricToCutting,
  verifyFabricReceipt,
} from "../api/operations";
import type {
  CapacityProfileCreate,
  CapacityStage,
  CuttingAnalysisCreate,
  FabricIssueToCuttingCreate,
  FabricMillOrderCreate,
  MillFollowUpCreate,
  MillOrderSplitCreate,
  UUID,
} from "../types/api";

export function useFabricMillOrders(purchaseOrderId?: UUID) {
  return useQuery({
    queryKey: ["fabricMillOrders", purchaseOrderId],
    queryFn: () => fetchFabricMillOrders(purchaseOrderId),
  });
}

export function useLateMillOrders() {
  return useQuery({
    queryKey: ["lateMillOrders"],
    queryFn: fetchLateMillOrders,
  });
}

export function useMillFollowupsDue() {
  return useQuery({
    queryKey: ["millFollowupsDue"],
    queryFn: fetchMillFollowupsDue,
  });
}

export function useFabricIssues(purchaseOrderId?: UUID) {
  return useQuery({
    queryKey: ["fabricIssues", purchaseOrderId],
    queryFn: () => fetchFabricIssues(purchaseOrderId),
  });
}

export function useCuttingAnalysis(purchaseOrderId?: UUID) {
  return useQuery({
    queryKey: ["cuttingAnalysis", purchaseOrderId],
    queryFn: () => fetchCuttingAnalysis(purchaseOrderId),
  });
}

export function useMillWastageHistory() {
  return useQuery({
    queryKey: ["millWastageHistory"],
    queryFn: fetchMillWastageHistory,
  });
}

export function useMillOrderSplits(purchaseOrderId?: UUID) {
  return useQuery({
    queryKey: ["millOrderSplits", purchaseOrderId],
    queryFn: () => fetchMillOrderSplits(purchaseOrderId),
  });
}

export function useCreateMillOrderSplit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MillOrderSplitCreate) => createMillOrderSplit(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["millOrderSplits"] });
      queryClient.invalidateQueries({ queryKey: ["fabricMillOrders"] });
      queryClient.invalidateQueries({ queryKey: ["reminders"] });
    },
  });
}

export function useMillWastageRecords(params?: { millName?: string; purchaseOrderId?: UUID }) {
  return useQuery({
    queryKey: ["millWastageRecords", params?.millName, params?.purchaseOrderId],
    queryFn: () => fetchMillWastageRecords(params),
  });
}

export function useReminders(status = "open") {
  return useQuery({
    queryKey: ["reminders", status],
    queryFn: () => fetchReminders(status),
  });
}

export function useDueReminders() {
  return useQuery({
    queryKey: ["dueReminders"],
    queryFn: fetchDueReminders,
  });
}

export function useCreateFabricMillOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FabricMillOrderCreate) => createFabricMillOrder(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fabricMillOrders"] });
      queryClient.invalidateQueries({ queryKey: ["lateMillOrders"] });
      queryClient.invalidateQueries({ queryKey: ["dueReminders"] });
    },
  });
}

export function useCreateMillFollowup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MillFollowUpCreate) => createMillFollowup(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["millFollowupsDue"] });
    },
  });
}

export function useVerifyFabricReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: verifyFabricReceipt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fabricReceipts"] });
    },
  });
}

export function useIssueFabricToCutting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FabricIssueToCuttingCreate) => issueFabricToCutting(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fabricIssues"] });
    },
  });
}

export function useCreateCuttingAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CuttingAnalysisCreate) => createCuttingAnalysis(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cuttingAnalysis"] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["millWastageHistory"] });
      queryClient.invalidateQueries({ queryKey: ["millWastageRecords"] });
    },
  });
}

export function useCompleteReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reminderId: UUID) => completeReminder(reminderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reminders"] });
      queryClient.invalidateQueries({ queryKey: ["dueReminders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useCapacityProfiles(activeOnly = true) {
  return useQuery({
    queryKey: ["capacityProfiles", activeOnly],
    queryFn: () => fetchCapacityProfiles(activeOnly),
  });
}

export function useCreateCapacityProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CapacityProfileCreate) => createCapacityProfile(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["capacityProfiles"] }),
  });
}

export function useCapacityForecast(purchaseOrderId: UUID | null, stage: CapacityStage) {
  return useQuery({
    queryKey: ["capacityForecast", purchaseOrderId, stage],
    queryFn: () => fetchCapacityForecast(purchaseOrderId as UUID, stage),
    enabled: Boolean(purchaseOrderId),
  });
}

export function useUnderutilization(stage: CapacityStage) {
  return useQuery({
    queryKey: ["underutilization", stage],
    queryFn: () => fetchUnderutilization(stage),
  });
}
