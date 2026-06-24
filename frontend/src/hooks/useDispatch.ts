import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { createDispatchLoad, deleteDispatchLoad, fetchDispatchLoads, updateDispatchLoad } from "../api/dispatch";
import type { DispatchLoadCreate, DispatchLoadUpdate, PurchaseOrderRead, UUID } from "../types/api";

export function useDispatchLoads(purchaseOrderId: UUID | undefined) {
  return useQuery({
    queryKey: ["dispatch-loads", purchaseOrderId],
    queryFn: () => fetchDispatchLoads(purchaseOrderId as UUID),
    enabled: Boolean(purchaseOrderId),
    staleTime: 30_000,
  });
}

export function useAllDispatchLoads(purchaseOrders: PurchaseOrderRead[] | undefined) {
  return useQueries({
    queries: (purchaseOrders ?? []).map((po) => ({
      queryKey: ["dispatch-loads", po.id],
      queryFn: () => fetchDispatchLoads(po.id),
      staleTime: 30_000,
    })),
  });
}

export function useCreateDispatchLoad() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: DispatchLoadCreate) => createDispatchLoad(payload),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dispatch-loads", variables.purchase_order_id] });
    },
  });
}

export function useUpdateDispatchLoad() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: DispatchLoadUpdate; purchaseOrderId: UUID }) =>
      updateDispatchLoad(id, payload),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dispatch-loads", variables.purchaseOrderId] });
    },
  });
}

export function useDeleteDispatchLoad() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: { id: UUID; purchaseOrderId: UUID }) => deleteDispatchLoad(id),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dispatch-loads", variables.purchaseOrderId] });
    },
  });
}
