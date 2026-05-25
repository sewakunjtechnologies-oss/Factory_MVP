import { api } from "./axios";
import type { ProductCreate, ProductRead, PurchaseOrderCreate, PurchaseOrderRead, UUID } from "../types/api";

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

export async function fetchProducts(): Promise<ProductRead[]> {
  const response = await api.get<ProductRead[]>("/products");
  return response.data;
}
