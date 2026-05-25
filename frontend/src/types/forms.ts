import type { DispatchCostType, UserRole, UUID } from "./api";

export interface LoginFormValues {
  email: string;
  password: string;
}

export interface RegisterFormValues {
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  role: UserRole;
}

export interface ProductionFormValues {
  purchase_order_id: UUID;
  stage: string;
  allocation_id: string;
  completed_today: string;
  approved_today: string;
  rejected_today: string;
  repair_today: string;
  alter_today: string;
  moved_to_next_stage_today: string;
  delay_days: string;
  remarks: string;
}

export interface DispatchFormValues {
  purchase_order_id: UUID;
  load_number: string;
  shipped_qty: string;
  vehicle_type: string;
  vehicle_identifier: string;
  expected_piece_capacity: string;
  actual_loaded_pieces: string;
  cbm_capacity: string;
  cbm_used: string;
  cost_type: DispatchCostType;
  invoice_value: string;
  dispatch_percent: string;
  cbm_value: string;
  cbm_rate: string;
  manual_cost: string;
  vehicle_cost: string;
  shipped_at: string;
  transporter_name: string;
  destination: string;
  tracking_reference: string;
  linked_repair_qty: string;
  linked_alteration_qty: string;
  shortfall_reason: string;
}
