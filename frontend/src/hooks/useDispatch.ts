import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { createDispatchLoad, fetchDispatchLoads } from "../api/dispatch";
import type { DispatchLoadCreate, PurchaseOrderRead, UUID } from "../types/api";

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
