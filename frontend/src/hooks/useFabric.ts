import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createFabricReceipt,
  fetchDebitNotes,
  fetchFabricReceipts,
  fetchFabricShortages,
  fetchSupplierReturns,
} from "../api/fabric";
import type { FabricReceiptCreate } from "../types/api";

export function useFabricShortages() {
  return useQuery({ queryKey: ["fabric-shortages"], queryFn: fetchFabricShortages, staleTime: 30_000 });
}

export function useFabricReceipts() {
  return useQuery({ queryKey: ["fabric-receipts"], queryFn: fetchFabricReceipts, staleTime: 30_000 });
}

export function useSupplierReturns() {
  return useQuery({ queryKey: ["supplier-returns"], queryFn: fetchSupplierReturns, staleTime: 30_000 });
}

export function useDebitNotes() {
  return useQuery({ queryKey: ["debit-notes"], queryFn: fetchDebitNotes, staleTime: 30_000 });
}

export function useCreateFabricReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FabricReceiptCreate) => createFabricReceipt(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["fabric-shortages"] });
      void queryClient.invalidateQueries({ queryKey: ["fabric-receipts"] });
      void queryClient.invalidateQueries({ queryKey: ["supplier-returns"] });
      void queryClient.invalidateQueries({ queryKey: ["debit-notes"] });
      void queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
