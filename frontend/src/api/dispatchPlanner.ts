import { api } from "./axios";
import type { UUID } from "../types/api";

export interface VehicleRead {
  id: UUID;
  name: string;
  registration_number: string | null;
  cbm_capacity: string;
  max_weight_kg: string;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DispatchPlanRequest {
  vehicle_id: UUID;
  category_priority: string[];
}

export interface DispatchPlanItem {
  product_fabric_line_id: UUID;
  category: string;
  fabric_code: string;
  bales: number;
  pieces: number;
  cbm: string;
  weight_kg: string;
}

export interface DispatchPlanLeftover {
  category: string;
  fabric_code: string;
  reason: string;
  available_pieces: number;
}

export interface DispatchPlanResponse {
  vehicle_id: UUID;
  vehicle_name: string;
  cbm_capacity: string;
  max_weight_kg: string;
  used_cbm: string;
  used_weight_kg: string;
  fill_pct_cbm: number;
  fill_pct_weight: number;
  total_bales: number;
  total_pieces: number;
  items: DispatchPlanItem[];
  leftover: DispatchPlanLeftover[];
}

export async function fetchVehicles(includeInactive = false): Promise<VehicleRead[]> {
  const response = await api.get<VehicleRead[]>("/vehicles", {
    params: includeInactive ? { include_inactive: true } : undefined,
  });
  return response.data;
}

export async function planDispatch(payload: DispatchPlanRequest): Promise<DispatchPlanResponse> {
  const response = await api.post<DispatchPlanResponse>("/dispatch/plan", payload);
  return response.data;
}
