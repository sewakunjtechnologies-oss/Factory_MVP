import { api } from "./axios";
import type {
  PackingMaterialBackfillSummary,
  PackingMaterialCategoryDemand,
  PackingMaterialCreate,
  PackingMaterialRead,
  PackingMaterialUpdate,
  UUID,
} from "../types/api";

export async function fetchPackingMaterials(params?: {
  purchase_order_id?: UUID;
  status?: string;
  search?: string;
}): Promise<PackingMaterialRead[]> {
  const response = await api.get<PackingMaterialRead[]>("/packing-materials", { params });
  return response.data;
}

export async function createPackingMaterial(payload: PackingMaterialCreate): Promise<PackingMaterialRead> {
  const response = await api.post<PackingMaterialRead>("/packing-materials", payload);
  return response.data;
}

export async function updatePackingMaterial(id: UUID, payload: PackingMaterialUpdate): Promise<PackingMaterialRead> {
  const response = await api.patch<PackingMaterialRead>(`/packing-materials/${id}`, payload);
  return response.data;
}

export async function deletePackingMaterial(id: UUID): Promise<void> {
  await api.delete(`/packing-materials/${id}`);
}

export async function backfillJunePackingMaterials(): Promise<PackingMaterialBackfillSummary> {
  const response = await api.post<PackingMaterialBackfillSummary>("/packing-materials/backfill-june");
  return response.data;
}

export async function fetchPackingMaterialCategoryDemand(): Promise<PackingMaterialCategoryDemand[]> {
  const response = await api.get<PackingMaterialCategoryDemand[]>("/packing-materials/category-demand");
  return response.data;
}
