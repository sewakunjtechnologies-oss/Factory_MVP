import { api } from "./axios";
import type {
  CapacityForecastRead,
  CapacityProfileCreate,
  CapacityProfileRead,
  CapacityStage,
  CuttingAnalysisCreate,
  CuttingAnalysisRead,
  FabricIssueToCuttingCreate,
  FabricIssueToCuttingRead,
  FabricMillOrderCreate,
  FabricMillOrderRead,
  FabricReceiptRead,
  MillFollowUpCreate,
  MillFollowUpRead,
  MillOrderSplitCreate,
  MillOrderSplitRead,
  MillWastageHistoryEntry,
  MillWastageRecordRead,
  ReminderRead,
  UnderutilizationRead,
  UUID,
} from "../types/api";

export async function createFabricMillOrder(payload: FabricMillOrderCreate): Promise<FabricMillOrderRead> {
  const response = await api.post<FabricMillOrderRead>("/fabric-operations/mill-orders", payload);
  return response.data;
}

export async function fetchFabricMillOrders(purchaseOrderId?: UUID): Promise<FabricMillOrderRead[]> {
  const response = await api.get<FabricMillOrderRead[]>("/fabric-operations/mill-orders", {
    params: purchaseOrderId ? { purchase_order_id: purchaseOrderId } : undefined,
  });
  return response.data;
}

export async function fetchLateMillOrders(): Promise<FabricMillOrderRead[]> {
  const response = await api.get<FabricMillOrderRead[]>("/fabric-operations/mill-orders/late");
  return response.data;
}

export async function createMillFollowup(payload: MillFollowUpCreate): Promise<MillFollowUpRead> {
  const response = await api.post<MillFollowUpRead>("/fabric-operations/mill-followups", payload);
  return response.data;
}

export async function fetchMillFollowupsDue(): Promise<MillFollowUpRead[]> {
  const response = await api.get<MillFollowUpRead[]>("/fabric-operations/mill-followups/due");
  return response.data;
}

export async function verifyFabricReceipt(payload: {
  receipt_id: UUID;
  verification_status: "pending" | "approved" | "mismatch" | "rejected" | "returned";
  action_taken: "accept" | "return_to_supplier" | "reopen_shortage" | "adjust_consumption" | "hold";
  verification_date: string;
  mismatch_reason?: string | null;
}): Promise<FabricReceiptRead> {
  const response = await api.post<FabricReceiptRead>("/fabric-operations/verify-receipt", payload);
  return response.data;
}

export async function issueFabricToCutting(payload: FabricIssueToCuttingCreate): Promise<FabricIssueToCuttingRead> {
  const response = await api.post<FabricIssueToCuttingRead>("/fabric-operations/issue-to-cutting", payload);
  return response.data;
}

export async function fetchFabricIssues(purchaseOrderId?: UUID): Promise<FabricIssueToCuttingRead[]> {
  const response = await api.get<FabricIssueToCuttingRead[]>("/fabric-operations/issue-to-cutting", {
    params: purchaseOrderId ? { purchase_order_id: purchaseOrderId } : undefined,
  });
  return response.data;
}

export async function createCuttingAnalysis(payload: CuttingAnalysisCreate): Promise<CuttingAnalysisRead> {
  const response = await api.post<CuttingAnalysisRead>("/fabric-operations/cutting-analysis", payload);
  return response.data;
}

export async function fetchCuttingAnalysis(purchaseOrderId?: UUID): Promise<CuttingAnalysisRead[]> {
  const response = await api.get<CuttingAnalysisRead[]>("/fabric-operations/cutting-analysis", {
    params: purchaseOrderId ? { purchase_order_id: purchaseOrderId } : undefined,
  });
  return response.data;
}

export async function createMillOrderSplit(payload: MillOrderSplitCreate): Promise<MillOrderSplitRead[]> {
  const response = await api.post<MillOrderSplitRead[]>("/fabric-operations/mill-orders/split", payload);
  return response.data;
}

export async function fetchMillOrderSplits(purchaseOrderId?: UUID): Promise<MillOrderSplitRead[]> {
  const response = await api.get<MillOrderSplitRead[]>("/fabric-operations/mill-orders/split", {
    params: purchaseOrderId ? { purchase_order_id: purchaseOrderId } : undefined,
  });
  return response.data;
}

export async function fetchMillWastageHistory(): Promise<MillWastageHistoryEntry[]> {
  const response = await api.get<MillWastageHistoryEntry[]>("/fabric-operations/mill-wastage-history");
  return response.data;
}

export async function fetchMillWastageRecords(params?: {
  millName?: string;
  purchaseOrderId?: UUID;
}): Promise<MillWastageRecordRead[]> {
  const response = await api.get<MillWastageRecordRead[]>("/fabric-operations/mill-wastage-records", {
    params: {
      mill_name: params?.millName,
      purchase_order_id: params?.purchaseOrderId,
    },
  });
  return response.data;
}

export async function fetchReminders(status = "open"): Promise<ReminderRead[]> {
  const response = await api.get<ReminderRead[]>("/reminders", { params: { status } });
  return response.data;
}

export async function fetchDueReminders(): Promise<ReminderRead[]> {
  const response = await api.get<ReminderRead[]>("/reminders/due");
  return response.data;
}

export async function completeReminder(reminderId: UUID): Promise<ReminderRead> {
  const response = await api.post<ReminderRead>(`/reminders/${reminderId}/complete`);
  return response.data;
}

export async function createCapacityProfile(payload: CapacityProfileCreate): Promise<CapacityProfileRead> {
  const response = await api.post<CapacityProfileRead>("/capacity/profiles", payload);
  return response.data;
}

export async function fetchCapacityProfiles(activeOnly = true): Promise<CapacityProfileRead[]> {
  const response = await api.get<CapacityProfileRead[]>("/capacity/profiles", { params: { active_only: activeOnly } });
  return response.data;
}

export async function fetchCapacityForecast(purchaseOrderId: UUID, stage: CapacityStage): Promise<CapacityForecastRead> {
  const response = await api.get<CapacityForecastRead>(`/capacity/forecast/${purchaseOrderId}`, { params: { stage } });
  return response.data;
}

export async function fetchUnderutilization(stage: CapacityStage): Promise<UnderutilizationRead> {
  const response = await api.get<UnderutilizationRead>("/capacity/underutilization", { params: { stage } });
  return response.data;
}
