import { api } from "./axios";
import type { UUID } from "../types/api";

export type StageStatus = "pending" | "in_progress" | "done";
export type StockStatus = "extra" | "in_stock" | "ok" | "nil" | "short" | "unknown";

export interface ProductFabricLineRead {
  id: UUID;
  product_id: UUID;
  fabric_code: string;
  pieces: number;
  pieces_in_stock: number;
  pieces_short: number;
  stock_status: StockStatus;
  per_piece_meters: string;
  stock_meters: string;
  pieces_per_bale: number;
  bale_size_cbm: string;
  bale_weight_kg: string;
  cutting: StageStatus;
  stitching: StageStatus;
  packing: StageStatus;
  dispatch: StageStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductFabricLineUpdate {
  pieces?: number;
  pieces_in_stock?: number;
  pieces_short?: number;
  stock_status?: StockStatus;
  per_piece_meters?: number;
  stock_meters?: number;
  pieces_per_bale?: number;
  bale_size_cbm?: number;
  bale_weight_kg?: number;
  cutting?: StageStatus;
  stitching?: StageStatus;
  packing?: StageStatus;
  dispatch?: StageStatus;
  notes?: string | null;
}

export interface PiecesReceiptCreate {
  product_fabric_line_id: UUID;
  pieces: number;
  received_at?: string;
  mill_name?: string | null;
  notes?: string | null;
}

export interface PiecesReceiptRead {
  id: UUID;
  product_fabric_line_id: UUID;
  pieces: number;
  received_at: string;
  mill_name: string | null;
  notes: string | null;
  created_by: UUID | null;
  created_at: string;
}

export async function createPiecesReceipt(payload: PiecesReceiptCreate): Promise<PiecesReceiptRead> {
  const response = await api.post<PiecesReceiptRead>("/pieces-receipts", payload);
  return response.data;
}

export async function fetchPiecesReceipts(productFabricLineId?: UUID): Promise<PiecesReceiptRead[]> {
  const response = await api.get<PiecesReceiptRead[]>("/pieces-receipts", {
    params: productFabricLineId ? { product_fabric_line_id: productFabricLineId } : undefined,
  });
  return response.data;
}

export interface FabricMeterReceiptCreate {
  product_fabric_line_id: UUID;
  meters: number;
  received_at?: string;
  mill_name?: string | null;
  notes?: string | null;
}

export interface FabricMeterReceiptRead {
  id: UUID;
  product_fabric_line_id: UUID;
  meters: string;
  received_at: string;
  mill_name: string | null;
  notes: string | null;
  created_by: UUID | null;
  created_at: string;
}

export async function createFabricMeterReceipt(payload: FabricMeterReceiptCreate): Promise<FabricMeterReceiptRead> {
  const response = await api.post<FabricMeterReceiptRead>("/fabric-meter-receipts", payload);
  return response.data;
}

export async function fetchProductFabricLines(productId?: UUID): Promise<ProductFabricLineRead[]> {
  const response = await api.get<ProductFabricLineRead[]>("/product-fabric-lines", {
    params: productId ? { product_id: productId } : undefined,
  });
  return response.data;
}

export async function updateProductFabricLine(id: UUID, payload: ProductFabricLineUpdate): Promise<ProductFabricLineRead> {
  const response = await api.patch<ProductFabricLineRead>(`/product-fabric-lines/${id}`, payload);
  return response.data;
}
