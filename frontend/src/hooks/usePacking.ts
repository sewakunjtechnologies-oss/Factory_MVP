import { useQuery } from "@tanstack/react-query";

import { api } from "../api/axios";
import type { PackingAnalysisRead, UUID } from "../types/api";

export function usePackingAnalysis(purchaseOrderId: UUID | undefined, avgPerPacker: number, actualPackers: number) {
  return useQuery({
    queryKey: ["packing-analysis", purchaseOrderId, avgPerPacker, actualPackers],
    queryFn: async () => {
      const response = await api.get<PackingAnalysisRead>(`/packing/purchase-orders/${purchaseOrderId}/analysis`, {
        params: { avg_per_packer: avgPerPacker, actual_packers: actualPackers },
      });
      return response.data;
    },
    enabled: Boolean(purchaseOrderId),
    staleTime: 20_000,
  });
}
