import { api } from "./axios";
import type {
  ContractorAllocationCreate,
  ContractorAllocationRead,
  QCInspectionCreate,
  QCInspectionRead,
  QualityFailureCreate,
  QualityFailureRead,
  StageProgressCreate,
  StageProgressRead,
  StageSummaryRead,
  UUID,
} from "../types/api";

export async function fetchStageSummaries(purchaseOrderId: UUID): Promise<StageSummaryRead[]> {
  const response = await api.get<StageSummaryRead[]>(
    `/stage-progress/purchase-orders/${purchaseOrderId}/summaries`,
  );
  return response.data;
}

export async function fetchAllocations(purchaseOrderId: UUID): Promise<ContractorAllocationRead[]> {
  const response = await api.get<ContractorAllocationRead[]>(
    `/stage-allocations/purchase-orders/${purchaseOrderId}`,
  );
  return response.data;
}

export async function fetchQualityFailures(purchaseOrderId: UUID): Promise<QualityFailureRead[]> {
  const response = await api.get<QualityFailureRead[]>(
    `/quality-failures/purchase-orders/${purchaseOrderId}`,
  );
  return response.data;
}

export async function fetchStageProgressEntries(purchaseOrderId: UUID): Promise<StageProgressRead[]> {
  const response = await api.get<StageProgressRead[]>(`/stage-progress/purchase-orders/${purchaseOrderId}/entries`);
  return response.data;
}

export async function submitStageProgress(payload: StageProgressCreate): Promise<unknown> {
  const response = await api.post("/stage-progress", payload);
  return response.data;
}

export async function createStageAllocation(payload: ContractorAllocationCreate): Promise<ContractorAllocationRead> {
  const response = await api.post<ContractorAllocationRead>("/stage-allocations", payload);
  return response.data;
}

export async function createQualityFailure(payload: QualityFailureCreate): Promise<QualityFailureRead> {
  const response = await api.post<QualityFailureRead>("/quality-failures", payload);
  return response.data;
}

export async function createQCInspection(payload: QCInspectionCreate): Promise<QCInspectionRead> {
  const response = await api.post<QCInspectionRead>("/quality-failures/qc-inspections", payload);
  return response.data;
}

export async function fetchQCInspections(purchaseOrderId: UUID): Promise<QCInspectionRead[]> {
  const response = await api.get<QCInspectionRead[]>(
    `/quality-failures/qc-inspections/purchase-orders/${purchaseOrderId}`,
  );
  return response.data;
}
