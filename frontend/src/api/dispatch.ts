import { api } from "./axios";
import type { DispatchLoadCreate, DispatchLoadRead, DispatchLoadUpdate, DispatchSummaryRead, UUID } from "../types/api";

export async function fetchDispatchLoads(purchaseOrderId: UUID): Promise<DispatchLoadRead[]> {
  const response = await api.get<DispatchLoadRead[]>(`/dispatch/purchase-orders/${purchaseOrderId}`);
  return response.data;
}

export async function createDispatchLoad(payload: DispatchLoadCreate): Promise<DispatchLoadRead> {
  const response = await api.post<DispatchLoadRead>("/dispatch", payload);
  return response.data;
}

export async function updateDispatchLoad(id: UUID, payload: DispatchLoadUpdate): Promise<DispatchLoadRead> {
  const response = await api.patch<DispatchLoadRead>(`/dispatch/${id}`, payload);
  return response.data;
}

export async function deleteDispatchLoad(id: UUID): Promise<void> {
  await api.delete(`/dispatch/${id}`);
}

export async function fetchDispatchSummary(purchaseOrderId: UUID): Promise<DispatchSummaryRead> {
  const response = await api.get<DispatchSummaryRead>(`/dispatch/purchase-orders/${purchaseOrderId}/summary`);
  return response.data;
}
