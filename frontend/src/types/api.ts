export type UUID = string;

export type UserRole = "owner" | "manager";
export type POStatus =
  | "draft"
  | "fabric_check_pending"
  | "fabric_ready"
  | "shortage"
  | "cutting"
  | "stitching"
  | "size_inspection"
  | "quality_check"
  | "packing"
  | "dispatch"
  | "partially_dispatched"
  | "dispatched_with_exception"
  | "completed"
  | "delayed"
  | "cancelled";

export type StageName =
  | "fabric_ready"
  | "cutting"
  | "stitching"
  | "size_inspection"
  | "quality_check"
  | "packing"
  | "dispatch";

export type StageStatus = "not_started" | "in_progress" | "completed" | "delayed" | "blocked";
export type AlertPriority = "low" | "medium" | "high" | "critical";
export type DispatchCostType = "invoice_percent" | "cbm" | "manual" | "vehicle_capacity";
export type FabricDesignCategory = "double_bed_sheet" | "single_bed_sheet" | "fitted_bed_sheet" | "king_bed_sheet" | "pillow" | "other";
export type PODesignStatus = "selected_from_library" | "custom_design" | "not_provided";
export type AlertType =
  | "stock_shortage"
  | "stage_delay"
  | "contractor_delay"
  | "shipment_risk"
  | "packing_risk"
  | "high_rejection";

export interface AuthUser {
  id: UUID;
  full_name: string;
  email: string;
  role: UserRole;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  full_name: string;
  email: string;
  password: string;
  role: UserRole;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
}

export interface ProductRead {
  id: UUID;
  product_name: string;
  product_category: string;
  size: string;
  design: string;
  color: string;
  fabric_type: string;
  gsm: string;
  width: string;
  per_piece_fabric_usage_m: string;
  wastage_percent: string;
  roll_length_m: string | null;
  product_photo_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface FabricPlanRead {
  id: UUID;
  purchase_order_id: UUID;
  required_m: string;
  wastage_m: string;
  total_required_m: string;
  roll_length_m: string | null;
  rolls_required: number | null;
  available_m: string;
  shortage_m: string;
  status: "fabric_ready" | "shortage";
  created_at: string;
  updated_at: string;
}

export interface StageSummaryRead {
  id: UUID;
  purchase_order_id: UUID;
  stage: StageName;
  sequence: number;
  input_qty: number;
  completed_qty: number;
  approved_qty: number;
  rejected_qty: number;
  repair_qty: number;
  alter_qty: number;
  moved_to_next_qty: number;
  pending_qty: number;
  status: StageStatus;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderRead {
  id: UUID;
  po_number: string;
  product_id: UUID;
  order_quantity_pcs: number;
  mrp: string | null;
  selling_price: string | null;
  order_date: string;
  promise_delivery_date: string;
  actual_delivery_date: string | null;
  status: POStatus;
  notes: string | null;
  fabric_design_id: UUID | null;
  design_name_snapshot: string | null;
  design_code_snapshot: string | null;
  design_image_url_snapshot: string | null;
  design_status: PODesignStatus;
  created_by: UUID | null;
  created_at: string;
  updated_at: string;
  product: ProductRead | null;
  fabric_plan: FabricPlanRead | null;
  stage_summaries: StageSummaryRead[];
  // Stock interlink — populated server-side from product_fabric_lines.
  pieces_in_stock_for_fabric: number;
  pieces_to_make: number;
}

export interface DashboardPORead {
  purchase_order_id: UUID;
  po_number: string;
  product: string;
  status: POStatus;
  order_quantity_pcs: number;
  completed_qty: number;
  pending_qty: number;
  bottleneck_stage: StageName | null;
  shipment_risk: boolean;
  next_urgent_action: string;
  fabric_shortage_m: number;
}

export interface AlertRead {
  id: UUID;
  purchase_order_id: UUID | null;
  alert_type: AlertType;
  priority: AlertPriority;
  title: string;
  message: string;
  is_resolved: boolean;
  created_at: string;
  resolved_at: string | null;
}

export interface OwnerDashboardRead {
  purchase_orders: DashboardPORead[];
  alerts: AlertRead[];
  reminders: ReminderRead[];
  active_pos: number;
  delayed_pos: number;
  fabric_shortages: number;
  shipment_risks: number;
  pending_dispatch: number;
  completed_today: number;
  top_bottleneck_stages: { stage: StageName; pending_qty: number; po_count: number }[];
  action_cards: { type: string; count: number; label: string }[];
}

export interface ContractorRead {
  id: UUID;
  name: string;
  contractor_type: string;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ContractorAllocationRead {
  id: UUID;
  stage_summary_id: UUID;
  stage: StageName;
  contractor_id: UUID;
  issued_qty: number;
  completed_qty: number;
  rejected_qty: number;
  repair_qty: number;
  alter_qty: number;
  delay_days: number;
  expected_completion_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface StageProgressCreate {
  purchase_order_id: UUID;
  stage: StageName;
  allocation_id?: UUID | null;
  entry_date: string;
  completed_today: number;
  approved_today: number;
  rejected_today: number;
  repair_today: number;
  alter_today: number;
  moved_to_next_stage_today: number;
  delay_days: number;
  remarks?: string | null;
}

export interface StageProgressRead {
  id: UUID;
  stage_summary_id: UUID;
  allocation_id: UUID | null;
  entry_date: string;
  completed_today: number;
  approved_today: number;
  rejected_today: number;
  repair_today: number;
  alter_today: number;
  moved_to_next_stage_today: number;
  delay_days: number;
  remarks: string | null;
  created_at: string;
}

export interface DispatchLoadRead {
  id: UUID;
  purchase_order_id: UUID;
  load_number: string;
  shipped_qty: number;
  vehicle_type: string | null;
  vehicle_identifier: string | null;
  expected_piece_capacity: number | null;
  actual_loaded_pieces: number | null;
  cbm_capacity: string | null;
  cbm_used: string | null;
  cost_type: DispatchCostType;
  invoice_value: string | null;
  dispatch_percent: string | null;
  cbm_value: string | null;
  cbm_rate: string | null;
  manual_cost: string | null;
  vehicle_cost: string | null;
  dispatch_cost: string;
  cost_per_piece: string;
  expected_cost_percent: string | null;
  actual_cost_percent: string | null;
  shipped_at: string;
  transporter_name: string | null;
  destination: string | null;
  tracking_reference: string | null;
  document_status: string | null;
  invoice_uploaded: boolean;
  packing_list_uploaded: boolean;
  eway_bill_uploaded: boolean;
  transporter_confirmation: boolean;
  buyer_dispatch_approval: boolean;
  shortfall_qty: number;
  shortfall_reason: string | null;
  linked_repair_qty: number;
  linked_alteration_qty: number;
  created_at: string;
}

export interface DispatchLoadCreate {
  purchase_order_id: UUID;
  load_number: string;
  shipped_qty: number;
  vehicle_type?: string | null;
  vehicle_identifier?: string | null;
  expected_piece_capacity?: number | null;
  actual_loaded_pieces?: number | null;
  cbm_capacity?: number | null;
  cbm_used?: number | null;
  cost_type: DispatchCostType;
  invoice_value?: number | null;
  dispatch_percent?: number | null;
  cbm_value?: number | null;
  cbm_rate?: number | null;
  manual_cost?: number | null;
  vehicle_cost?: number | null;
  shipped_at: string;
  transporter_name?: string | null;
  destination?: string | null;
  tracking_reference?: string | null;
  shortfall_reason?: string | null;
  linked_repair_qty?: number;
  linked_alteration_qty?: number;
}

export interface DispatchLoadUpdate {
  load_number?: string;
  shipped_qty?: number;
  vehicle_type?: string | null;
  vehicle_identifier?: string | null;
  expected_piece_capacity?: number | null;
  actual_loaded_pieces?: number | null;
  cbm_capacity?: number | null;
  cbm_used?: number | null;
  cost_type?: DispatchCostType;
  invoice_value?: number | null;
  dispatch_percent?: number | null;
  cbm_value?: number | null;
  cbm_rate?: number | null;
  manual_cost?: number | null;
  vehicle_cost?: number | null;
  shipped_at?: string;
  transporter_name?: string | null;
  destination?: string | null;
  tracking_reference?: string | null;
  document_status?: string | null;
  invoice_uploaded?: boolean;
  packing_list_uploaded?: boolean;
  eway_bill_uploaded?: boolean;
  transporter_confirmation?: boolean;
  buyer_dispatch_approval?: boolean;
  shortfall_reason?: string | null;
  linked_repair_qty?: number;
  linked_alteration_qty?: number;
}

export interface PackingAnalysisRead {
  purchase_order_id: UUID;
  remaining_qty: number;
  days_left: number;
  avg_per_packer: number;
  actual_packers: number;
  daily_target: number;
  required_packers: number;
  pieces_per_packer_per_day: number;
  packing_risk: boolean;
}

export type QualityAction = "repair_in_factory" | "return_to_contractor" | "reject";

export interface QualityFailureRead {
  id: UUID;
  stage_summary_id: UUID;
  allocation_id: UUID | null;
  failed_qty: number;
  resolved_qty: number;
  pending_resolution_qty: number;
  action: QualityAction;
  reason: string;
  resolution: string | null;
  action_date: string;
  created_at: string;
}

export interface ProductCreate {
  product_name: string;
  product_category: string;
  size: string;
  design: string;
  // Detected from product photo by AI vision — not entered by clients.
  color?: string | null;
  fabric_type: string;
  gsm: number;
  // Inferred from `size` server-side — not entered by clients.
  width?: number | null;
  per_piece_fabric_usage_m: number;
  wastage_percent: number;
  roll_length_m?: number | null;
  product_photo_url?: string | null;
}

export interface PurchaseOrderCreate {
  po_number: string;
  product_id: UUID;
  order_quantity_pcs: number;
  mrp?: number | null;
  selling_price?: number | null;
  order_date: string;
  promise_delivery_date: string;
  notes?: string | null;
  fabric_design_id?: UUID | null;
  custom_design_name?: string | null;
  custom_design_photo_url?: string | null;
  save_custom_design_to_library?: boolean;
}

export interface FabricDesignRead {
  id: UUID;
  category: FabricDesignCategory;
  design_name: string;
  design_code: string;
  image_url: string | null;
  color_tags: string[] | null;
  description: string | null;
  is_active: boolean;
  created_by: UUID | null;
  created_at: string;
  updated_at: string;
}

export interface FabricDesignCreate {
  category: FabricDesignCategory;
  design_name?: string | null;
  design_code?: string | null;
  image_url?: string | null;
  color_tags?: string[] | null;
  description?: string | null;
  is_active?: boolean;
}

export interface FabricDesignUpdate {
  category?: FabricDesignCategory;
  design_name?: string | null;
  design_code?: string | null;
  image_url?: string | null;
  color_tags?: string[] | null;
  description?: string | null;
  is_active?: boolean;
}

export interface ContractorAllocationCreate {
  stage_summary_id: UUID;
  contractor_id: UUID;
  issued_qty: number;
  expected_completion_date?: string | null;
  notes?: string | null;
}

export interface QualityFailureCreate {
  stage_summary_id: UUID;
  allocation_id?: UUID | null;
  failed_qty: number;
  resolved_qty: number;
  action: QualityAction;
  reason: string;
  resolution?: string | null;
  action_date: string;
}

export interface FabricReceiptCreate {
  purchase_order_id?: UUID | null;
  supplier_name: string;
  fabric_type: string;
  color: string;
  gsm: number;
  width: number;
  available_length_m: number;
  approximate_rolls?: number | null;
  status: "approved" | "failed";
  quality_notes?: string | null;
  received_width?: number | null;
  received_gsm?: number | null;
  received_rate_per_meter?: number | null;
  received_meters?: number | null;
  verification_status?: "pending" | "approved" | "mismatch" | "rejected" | "returned";
  action_taken?: "accept" | "return_to_supplier" | "reopen_shortage" | "adjust_consumption" | "hold" | null;
  mismatch_reason?: string | null;
  received_at: string;
  debit_amount?: number | null;
}

export interface FabricReceiptRead {
  id: UUID;
  purchase_order_id: UUID | null;
  supplier_name: string;
  fabric_type: string;
  color: string;
  gsm: string;
  width: string;
  received_length_m: string;
  approximate_rolls: number | null;
  status: "pending" | "approved" | "failed" | "returned";
  quality_notes: string | null;
  verification_status: "pending" | "approved" | "mismatch" | "rejected" | "returned";
  action_taken: "accept" | "return_to_supplier" | "reopen_shortage" | "adjust_consumption" | "hold" | null;
  mismatch_reason: string | null;
  received_at: string;
  created_at: string;
}

export type FabricMillOrderStatus = "not_ordered" | "ordered" | "in_followup" | "partially_received" | "received" | "delayed" | "cancelled";

export interface FabricMillOrderCreate {
  purchase_order_id: UUID;
  mill_name: string;
  ordered_meters: number;
  ordered_width?: number | null;
  ordered_gsm?: number | null;
  ordered_rate_per_meter?: number | null;
  expected_quality_notes?: string | null;
  committed_delivery_date: string;
  status?: FabricMillOrderStatus;
}

export interface FabricMillOrderRead extends FabricMillOrderCreate {
  id: UUID;
  invoice_number: string | null;
  actual_delivery_date: string | null;
  responsible_user_id: UUID | null;
  created_at: string;
  updated_at: string;
}

export interface MillFollowUpCreate {
  mill_order_id: UUID;
  followup_date: string;
  response_notes?: string | null;
  next_followup_date?: string | null;
  status?: FabricMillOrderStatus;
}

export interface MillFollowUpRead extends MillFollowUpCreate {
  id: UUID;
  followup_by: UUID | null;
  created_at: string;
  updated_at: string;
}

export interface FabricIssueToCuttingCreate {
  purchase_order_id: UUID;
  fabric_inventory_id?: UUID | null;
  fabric_receipt_id?: UUID | null;
  issued_meters: number;
  issued_rolls?: number | null;
  issue_date: string;
  remarks?: string | null;
}

export interface FabricIssueToCuttingRead extends FabricIssueToCuttingCreate {
  id: UUID;
  issued_by: UUID | null;
  received_by: UUID | null;
  created_at: string;
}

export interface CuttingAnalysisCreate {
  purchase_order_id: UUID;
  planned_cut_size?: string | null;
  actual_cut_size?: string | null;
  planned_consumption_m: number;
  actual_consumption_m: number;
  planned_wastage_m: number;
  actual_wastage_m: number;
  reason_for_difference?: string | null;
  mill_name?: string | null;
}

export interface CuttingAnalysisRead extends CuttingAnalysisCreate {
  id: UUID;
  wastage_difference_m: string;
  created_at: string;
  updated_at: string;
}

export interface QCInspectionCreate {
  purchase_order_id: UUID;
  stage: StageName;
  inspected_qty: number;
  size_ok: boolean;
  stitching_ok: boolean;
  shape_ok: boolean;
  fabric_defect_found: boolean;
  defect_notes?: string | null;
  passed_qty: number;
  failed_qty: number;
  repair_qty: number;
  alteration_qty: number;
  rejected_qty: number;
  inspection_date: string;
  remarks?: string | null;
}

export interface QCInspectionRead extends QCInspectionCreate {
  id: UUID;
  inspected_by: UUID | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface MillSplitItem {
  mill_name: string;
  split_percent: number;
  committed_delivery_date: string;
  ordered_width?: number | null;
  ordered_gsm?: number | null;
  ordered_rate_per_meter?: number | null;
}

export interface MillOrderSplitCreate {
  purchase_order_id: UUID;
  mill_order_requirement_id?: UUID | null;
  splits: MillSplitItem[];
}

export interface MillOrderSplitRead {
  id: UUID;
  purchase_order_id: UUID;
  mill_order_requirement_id: UUID | null;
  mill_name: string;
  split_percent: string;
  ordered_meters: string;
  committed_delivery_date: string;
  status: string;
  responsible_user_id: UUID | null;
  created_at: string;
  updated_at: string;
}

export interface MillWastageHistoryEntry {
  mill_name: string;
  event_count: number;
  total_planned_wastage_m: string;
  total_actual_wastage_m: string;
  total_difference_m: string;
  avg_difference_m: string;
  last_recorded_at: string | null;
  flag: "high" | "low" | "normal";
}

export interface MillWastageRecordRead {
  id: UUID;
  purchase_order_id: UUID;
  mill_name: string;
  cutting_analysis_id: UUID | null;
  planned_wastage_m: string;
  actual_wastage_m: string;
  wastage_difference_m: string;
  flag: "high" | "low" | "normal";
  recorded_by: UUID | null;
  recorded_at: string;
}

export interface ReminderRead {
  id: UUID;
  purchase_order_id: UUID | null;
  reminder_type: string;
  title: string;
  message: string;
  due_date: string;
  assigned_to: UUID | null;
  priority: "low" | "medium" | "high" | "critical";
  status: "open" | "completed" | "cancelled";
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export type CapacityStage = "cutting" | "stitching" | "packing";
export type CapacityProductType = "single_bedsheet" | "double_bedsheet" | "king_bedsheet" | "pillow" | "fitted_sheet" | "other";

export interface CapacityProfileCreate {
  product_type: CapacityProductType;
  stage: CapacityStage;
  daily_capacity_qty: number;
  worker_count: number;
  overtime_allowed: boolean;
  include_sunday: boolean;
  effective_from: string;
  is_active: boolean;
}

export interface CapacityProfileRead extends CapacityProfileCreate {
  id: UUID;
  created_at: string;
  updated_at: string;
}

export interface CapacityForecastRead {
  purchase_order_id: UUID;
  po_number: string;
  product_type: CapacityProductType;
  order_quantity_pcs: number;
  stage: CapacityStage;
  daily_capacity_qty: number;
  worker_count: number;
  days_required: number;
  forecast_completion_date: string;
  promise_delivery_date: string;
  shipment_risk: boolean;
}

export interface UnderutilizationRead {
  stage: CapacityStage;
  idle_date: string;
  available_capacity_qty: number;
  risk_type: string;
  message: string;
}

export interface SupplierReturnRead {
  id: UUID;
  fabric_receipt_id: UUID;
  supplier_name: string;
  returned_length_m: string;
  reason: string;
  returned_at: string;
  created_at: string;
}

export interface DebitNoteRead {
  id: UUID;
  fabric_receipt_id: UUID;
  supplier_name: string;
  amount: string | null;
  reason: string;
  note_date: string;
  created_at: string;
}

export interface FabricReceiptResult {
  receipt: FabricReceiptRead;
  supplier_return: SupplierReturnRead | null;
  debit_note: DebitNoteRead | null;
  refreshed_plan: FabricPlanRead | null;
}

export interface DispatchSummaryRead {
  purchase_order_id: UUID;
  total_dispatched: number;
  pending_dispatch: number;
  total_dispatch_cost: string;
  average_cost_per_piece: string;
  loads: DispatchLoadRead[];
}

export type PackingMaterialStatus = "in_stock" | "ordered" | "received" | "shortage" | "consumed" | "unknown";

export interface PackingMaterialRead {
  id: UUID;
  purchase_order_id: UUID | null;
  po_number: string | null;
  category_name: string;
  material_name: string;
  material_type: string;
  unit: string;
  required_qty: string;
  in_stock_qty: string;
  ordered_qty: string;
  received_qty: string;
  consumed_qty: string;
  printed_consumption_qty: string;
  actual_consumption_qty: string;
  printed_stock_qty: string;
  actual_stock_qty: string;
  shortage_qty: string;
  status: PackingMaterialStatus;
  supplier_name: string | null;
  expected_delivery_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PackingMaterialCreate {
  purchase_order_id?: UUID | null;
  po_number?: string | null;
  category_name: string;
  material_name: string;
  material_type?: string;
  unit?: string;
  required_qty?: number;
  in_stock_qty?: number;
  ordered_qty?: number;
  received_qty?: number;
  consumed_qty?: number;
  printed_consumption_qty?: number;
  actual_consumption_qty?: number;
  printed_stock_qty?: number;
  actual_stock_qty?: number;
  shortage_qty?: number;
  status?: PackingMaterialStatus;
  supplier_name?: string | null;
  expected_delivery_date?: string | null;
  notes?: string | null;
}

export interface PackingMaterialUpdate {
  purchase_order_id?: UUID | null;
  po_number?: string | null;
  category_name?: string;
  material_name?: string;
  material_type?: string;
  unit?: string;
  required_qty?: number;
  in_stock_qty?: number;
  ordered_qty?: number;
  received_qty?: number;
  consumed_qty?: number;
  printed_consumption_qty?: number;
  actual_consumption_qty?: number;
  printed_stock_qty?: number;
  actual_stock_qty?: number;
  shortage_qty?: number;
  status?: PackingMaterialStatus;
  supplier_name?: string | null;
  expected_delivery_date?: string | null;
  notes?: string | null;
}

export interface PackingMaterialBackfillSummary {
  rows_created: number;
  rows_updated: number;
  purchase_orders_scanned: number;
}

export interface PackingMaterialCategoryDemand {
  category: string;
  order_count: number;
  total_pieces: number;
  material_rule: string;
}
