import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  backfillJunePackingMaterials,
  createPackingMaterial,
  deletePackingMaterial,
  fetchPackingMaterialCategoryDemand,
  fetchPackingMaterials,
  updatePackingMaterial,
} from "../api/packingMaterials";
import type { PackingMaterialCreate, PackingMaterialUpdate, UUID } from "../types/api";

export function usePackingMaterials(filters: { status?: string; search?: string } = {}) {
  return useQuery({
    queryKey: ["packing-materials", filters],
    queryFn: () => fetchPackingMaterials(filters),
    staleTime: 15_000,
  });
}

export function useCreatePackingMaterial() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PackingMaterialCreate) => createPackingMaterial(payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["packing-materials"] }),
  });
}

export function useUpdatePackingMaterial() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: PackingMaterialUpdate }) => updatePackingMaterial(id, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["packing-materials"] }),
  });
}

export function useDeletePackingMaterial() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => deletePackingMaterial(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["packing-materials"] }),
  });
}

export function useBackfillJunePackingMaterials() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: backfillJunePackingMaterials,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["packing-materials"] });
      void queryClient.invalidateQueries({ queryKey: ["packing-material-category-demand"] });
    },
  });
}

export function usePackingMaterialCategoryDemand(enabled = true) {
  return useQuery({
    queryKey: ["packing-material-category-demand"],
    queryFn: fetchPackingMaterialCategoryDemand,
    enabled,
    staleTime: 30_000,
  });
}
