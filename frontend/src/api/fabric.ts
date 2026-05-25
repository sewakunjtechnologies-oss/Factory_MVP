import { api } from "./axios";
import type {
  DebitNoteRead,
  FabricPlanRead,
  FabricReceiptCreate,
  FabricReceiptRead,
  FabricReceiptResult,
  SupplierReturnRead,
} from "../types/api";

export async function fetchFabricShortages(): Promise<FabricPlanRead[]> {
  const response = await api.get<FabricPlanRead[]>("/fabric-shortages");
  return response.data;
}

export async function fetchFabricReceipts(): Promise<FabricReceiptRead[]> {
  const response = await api.get<FabricReceiptRead[]>("/fabric-receipts");
  return response.data;
}

export async function fetchSupplierReturns(): Promise<SupplierReturnRead[]> {
  const response = await api.get<SupplierReturnRead[]>("/fabric-receipts/supplier-returns");
  return response.data;
}

export async function fetchDebitNotes(): Promise<DebitNoteRead[]> {
  const response = await api.get<DebitNoteRead[]>("/fabric-receipts/debit-notes");
  return response.data;
}

export async function createFabricReceipt(payload: FabricReceiptCreate): Promise<FabricReceiptResult> {
  const response = await api.post<FabricReceiptResult>("/fabric-receipts", payload);
  return response.data;
}
