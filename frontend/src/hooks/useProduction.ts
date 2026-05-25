import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createQCInspection,
  createQualityFailure,
  createStageAllocation,
  fetchAllocations,
  fetchQCInspections,
  fetchQualityFailures,
  fetchStageProgressEntries,
  fetchStageSummaries,
  submitStageProgress,
} from "../api/production";
import type {
  ContractorAllocationCreate,
  QCInspectionCreate,
  QualityFailureCreate,
  StageProgressCreate,
  UUID,
} from "../types/api";

export function useStageSummaries(purchaseOrderId: UUID | undefined) {
  return useQuery({
    queryKey: ["stage-summaries", purchaseOrderId],
    queryFn: () => fetchStageSummaries(purchaseOrderId as UUID),
    enabled: Boolean(purchaseOrderId),
    staleTime: 20_000,
  });
}

export function useAllocations(purchaseOrderId: UUID | undefined) {
  return useQuery({
    queryKey: ["allocations", purchaseOrderId],
    queryFn: () => fetchAllocations(purchaseOrderId as UUID),
    enabled: Boolean(purchaseOrderId),
    staleTime: 20_000,
  });
}

export function useQualityFailures(purchaseOrderId: UUID | undefined) {
  return useQuery({
    queryKey: ["quality-failures", purchaseOrderId],
    queryFn: () => fetchQualityFailures(purchaseOrderId as UUID),
    enabled: Boolean(purchaseOrderId),
    staleTime: 20_000,
  });
}

export function useStageProgressEntries(purchaseOrderId: UUID | undefined) {
  return useQuery({
    queryKey: ["stage-progress-entries", purchaseOrderId],
    queryFn: () => fetchStageProgressEntries(purchaseOrderId as UUID),
    enabled: Boolean(purchaseOrderId),
    staleTime: 20_000,
  });
}

export function useSubmitStageProgress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: StageProgressCreate) => submitStageProgress(payload),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["stage-summaries", variables.purchase_order_id] });
      void queryClient.invalidateQueries({ queryKey: ["stage-progress-entries", variables.purchase_order_id] });
      void queryClient.invalidateQueries({ queryKey: ["allocations", variables.purchase_order_id] });
    },
  });
}

export function useCreateStageAllocation(purchaseOrderId?: UUID) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: ContractorAllocationCreate) => createStageAllocation(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      if (purchaseOrderId) {
        void queryClient.invalidateQueries({ queryKey: ["allocations", purchaseOrderId] });
      }
    },
  });
}

export function useCreateQualityFailure(purchaseOrderId?: UUID) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: QualityFailureCreate) => createQualityFailure(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (purchaseOrderId) {
        void queryClient.invalidateQueries({ queryKey: ["quality-failures", purchaseOrderId] });
      }
    },
  });
}

export function useQCInspections(purchaseOrderId: UUID | undefined) {
  return useQuery({
    queryKey: ["qc-inspections", purchaseOrderId],
    queryFn: () => fetchQCInspections(purchaseOrderId as UUID),
    enabled: Boolean(purchaseOrderId),
    staleTime: 20_000,
  });
}

export function useCreateQCInspection(purchaseOrderId?: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: QCInspectionCreate) => createQCInspection(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (purchaseOrderId) {
        void queryClient.invalidateQueries({ queryKey: ["qc-inspections", purchaseOrderId] });
        void queryClient.invalidateQueries({ queryKey: ["stage-summaries", purchaseOrderId] });
      }
    },
  });
}
