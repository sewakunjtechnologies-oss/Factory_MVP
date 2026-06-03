import { api } from "./axios";
import type { ProductCreate, ProductRead, PurchaseOrderCreate, PurchaseOrderRead, UUID } from "../types/api";

export interface PurchaseOrderUpdate {
  po_number?: string;
  product_id?: UUID;
  order_quantity_pcs?: number;
  mrp?: number | null;
  selling_price?: number | null;
  order_date?: string;
  promise_delivery_date?: string;
  actual_delivery_date?: string | null;
  status?: string;
  notes?: string | null;
  design_name_snapshot?: string | null;
  design_code_snapshot?: string | null;
  priority_level?: string | null;
  priority_reason?: string | null;
}

export async function fetchPurchaseOrders(): Promise<PurchaseOrderRead[]> {
  const response = await api.get<PurchaseOrderRead[]>("/purchase-orders");
  return response.data;
}

export async function fetchPurchaseOrder(id: UUID): Promise<PurchaseOrderRead> {
  const response = await api.get<PurchaseOrderRead>(`/purchase-orders/${id}`);
  return response.data;
}

export async function createProduct(payload: ProductCreate): Promise<ProductRead> {
  const response = await api.post<ProductRead>("/products", payload);
  return response.data;
}

export async function createPurchaseOrder(payload: PurchaseOrderCreate): Promise<PurchaseOrderRead> {
  const response = await api.post<PurchaseOrderRead>("/purchase-orders", payload);
  return response.data;
}

export async function updatePurchaseOrder(id: UUID, payload: PurchaseOrderUpdate): Promise<PurchaseOrderRead> {
  const response = await api.patch<PurchaseOrderRead>(`/purchase-orders/${id}`, payload);
  return response.data;
}

export async function deletePurchaseOrder(id: UUID): Promise<void> {
  await api.delete(`/purchase-orders/${id}`);
}

export async function fetchProducts(): Promise<ProductRead[]> {
  const response = await api.get<ProductRead[]>("/products");
  return response.data;
}
