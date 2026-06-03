import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProduct,
  createPurchaseOrder,
  deletePurchaseOrder,
  fetchProducts,
  fetchPurchaseOrder,
  fetchPurchaseOrders,
  updatePurchaseOrder,
  type PurchaseOrderUpdate,
} from "../api/purchaseOrders";
import type { ProductCreate, PurchaseOrderCreate, UUID } from "../types/api";

export function usePurchaseOrders() {
  return useQuery({
    queryKey: ["purchase-orders"],
    queryFn: fetchPurchaseOrders,
    staleTime: 30_000,
  });
}

export function usePurchaseOrder(id: UUID | undefined) {
  return useQuery({
    queryKey: ["purchase-orders", id],
    queryFn: () => fetchPurchaseOrder(id as UUID),
    enabled: Boolean(id),
    staleTime: 30_000,
  });
}

export function useProducts() {
  return useQuery({
    queryKey: ["products"],
    queryFn: fetchProducts,
    staleTime: 60_000,
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProductCreate) => createProduct(payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PurchaseOrderCreate) => createPurchaseOrder(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: PurchaseOrderUpdate }) =>
      updatePurchaseOrder(id, payload),
    onSuccess: (_, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders", id] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useDeletePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => deletePurchaseOrder(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

