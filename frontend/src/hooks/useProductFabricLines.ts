import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createFabricMeterReceipt,
  createPiecesReceipt,
  fetchProductFabricLines,
  updateProductFabricLine,
  type FabricMeterReceiptCreate,
  type PiecesReceiptCreate,
  type ProductFabricLineRead,
  type ProductFabricLineUpdate,
} from "../api/productFabricLines";
import type { UUID } from "../types/api";

export function useProductFabricLines(productId?: UUID) {
  return useQuery({
    queryKey: ["product-fabric-lines", productId ?? "all"],
    queryFn: () => fetchProductFabricLines(productId),
    staleTime: 15_000,
  });
}

export function useUpdateProductFabricLine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: ProductFabricLineUpdate }) =>
      updateProductFabricLine(id, payload),
    onMutate: async ({ id, payload }) => {
      await queryClient.cancelQueries({ queryKey: ["product-fabric-lines"] });
      const snapshots = queryClient.getQueriesData<ProductFabricLineRead[]>({ queryKey: ["product-fabric-lines"] });
      snapshots.forEach(([key, rows]) => {
        if (!rows) return;
        queryClient.setQueryData<ProductFabricLineRead[]>(
          key,
          rows.map((row) => (row.id === id ? { ...row, ...patchToRow(payload) } : row)),
        );
      });
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      ctx?.snapshots.forEach(([key, rows]) => queryClient.setQueryData(key, rows));
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["product-fabric-lines"] });
    },
  });
}

export function useReceivePieces() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PiecesReceiptCreate) => createPiecesReceipt(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["product-fabric-lines"] });
      void queryClient.invalidateQueries({ queryKey: ["pieces-receipts"] });
    },
  });
}

export function useReceiveFabricMeters() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FabricMeterReceiptCreate) => createFabricMeterReceipt(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["product-fabric-lines"] });
      void queryClient.invalidateQueries({ queryKey: ["fabric-meter-receipts"] });
    },
  });
}

function patchToRow(p: ProductFabricLineUpdate): Partial<ProductFabricLineRead> {
  const out: Partial<ProductFabricLineRead> = {};
  if (p.pieces !== undefined) out.pieces = p.pieces;
  if (p.pieces_in_stock !== undefined) out.pieces_in_stock = p.pieces_in_stock;
  if (p.pieces_short !== undefined) out.pieces_short = p.pieces_short;
  if (p.stock_status !== undefined) out.stock_status = p.stock_status;
  if (p.per_piece_meters !== undefined) out.per_piece_meters = String(p.per_piece_meters);
  if (p.stock_meters !== undefined) out.stock_meters = String(p.stock_meters);
  if (p.cutting !== undefined) out.cutting = p.cutting;
  if (p.stitching !== undefined) out.stitching = p.stitching;
  if (p.packing !== undefined) out.packing = p.packing;
  if (p.dispatch !== undefined) out.dispatch = p.dispatch;
  if (p.notes !== undefined) out.notes = p.notes;
  return out;
}
