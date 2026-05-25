import type { DispatchFormValues, ProductionFormValues } from "../types/forms";
import type { DispatchLoadCreate, StageName, StageProgressCreate } from "../types/api";

export function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function buildProductionPayload(values: ProductionFormValues): StageProgressCreate {
  return {
    purchase_order_id: values.purchase_order_id,
    stage: values.stage as StageName,
    allocation_id: values.allocation_id || null,
    entry_date: todayISO(),
    completed_today: toNumber(values.completed_today),
    approved_today: toNumber(values.approved_today),
    rejected_today: toNumber(values.rejected_today),
    repair_today: toNumber(values.repair_today),
    alter_today: toNumber(values.alter_today),
    moved_to_next_stage_today: toNumber(values.moved_to_next_stage_today),
    delay_days: toNumber(values.delay_days),
    remarks: values.remarks || null,
  };
}

export function buildDispatchPayload(values: DispatchFormValues): DispatchLoadCreate {
  const payload: DispatchLoadCreate = {
    purchase_order_id: values.purchase_order_id,
    load_number: values.load_number,
    shipped_qty: toNumber(values.shipped_qty),
    vehicle_type: values.vehicle_type || null,
    vehicle_identifier: values.vehicle_identifier || null,
    expected_piece_capacity: values.expected_piece_capacity ? toNumber(values.expected_piece_capacity) : null,
    actual_loaded_pieces: values.actual_loaded_pieces ? toNumber(values.actual_loaded_pieces) : null,
    cbm_capacity: values.cbm_capacity ? toNumber(values.cbm_capacity) : null,
    cbm_used: values.cbm_used ? toNumber(values.cbm_used) : null,
    cost_type: values.cost_type,
    shipped_at: values.shipped_at,
    transporter_name: values.transporter_name || null,
    destination: values.destination || null,
    tracking_reference: values.tracking_reference || null,
    linked_repair_qty: values.linked_repair_qty ? toNumber(values.linked_repair_qty) : 0,
    linked_alteration_qty: values.linked_alteration_qty ? toNumber(values.linked_alteration_qty) : 0,
    shortfall_reason: values.shortfall_reason || null,
  };
  if (values.cost_type === "invoice_percent") {
    payload.invoice_value = toNumber(values.invoice_value);
    payload.dispatch_percent = toNumber(values.dispatch_percent);
  } else if (values.cost_type === "cbm") {
    payload.cbm_value = toNumber(values.cbm_value);
    payload.cbm_rate = toNumber(values.cbm_rate);
  } else if (values.cost_type === "manual") {
    payload.manual_cost = toNumber(values.manual_cost);
  } else {
    payload.vehicle_cost = toNumber(values.vehicle_cost);
    if (!payload.actual_loaded_pieces) {
      payload.actual_loaded_pieces = toNumber(values.shipped_qty);
    }
  }
  return payload;
}
