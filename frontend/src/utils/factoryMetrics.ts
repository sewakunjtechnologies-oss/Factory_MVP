import type {
  AlertRead,
  DashboardPORead,
  DispatchLoadRead,
  PurchaseOrderRead,
  StageName,
  StageSummaryRead,
} from "../types/api";

export const productionStages: StageName[] = [
  "cutting",
  "stitching",
  "size_inspection",
  "quality_check",
  "packing",
];

export interface DashboardMetrics {
  activePOs: number;
  delayedPOs: number;
  shipmentRisk: number;
  fabricShortage: number;
  pendingDispatch: number;
  completedToday: number;
}

export function getDashboardMetrics(pos: DashboardPORead[], alerts: AlertRead[], purchaseOrders: PurchaseOrderRead[] = []): DashboardMetrics {
  const today = new Date().toISOString().slice(0, 10);
  return {
    activePOs: pos.filter((po) => !["completed", "cancelled"].includes(po.status)).length,
    delayedPOs: alerts.filter((alert) => alert.alert_type === "stage_delay" || alert.alert_type === "contractor_delay")
      .length,
    shipmentRisk: pos.filter((po) => po.shipment_risk).length,
    fabricShortage: alerts.filter((alert) => alert.alert_type === "stock_shortage").length,
    pendingDispatch: pos.filter((po) => po.pending_qty > 0 && ["dispatch", "partially_dispatched"].includes(po.status))
      .length,
    completedToday: purchaseOrders.filter((po) => po.actual_delivery_date === today).length,
  };
}

export function getStageProgressPercent(stage: StageSummaryRead): number {
  if (stage.input_qty <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((stage.approved_qty / stage.input_qty) * 100));
}

export function getPOCompletedQty(po: PurchaseOrderRead): number {
  const dispatch = po.stage_summaries.find((stage) => stage.stage === "dispatch");
  return dispatch?.completed_qty ?? 0;
}

export function getPOPackedQty(po: PurchaseOrderRead): number {
  const packing = po.stage_summaries.find((stage) => stage.stage === "packing");
  return packing?.approved_qty ?? 0;
}

export function getPOPendingQty(po: PurchaseOrderRead): number {
  return Math.max(po.order_quantity_pcs - getPOCompletedQty(po), 0);
}

export function getBottleneckStage(po: PurchaseOrderRead): StageSummaryRead | null {
  const activeStages = po.stage_summaries.filter((stage) => stage.stage !== "dispatch" && stage.pending_qty > 0);
  if (activeStages.length === 0) {
    return null;
  }
  return activeStages.reduce((winner, stage) => (stage.pending_qty > winner.pending_qty ? stage : winner));
}

export function getLoadTotals(loads: DispatchLoadRead[]) {
  return loads.reduce(
    (total, load) => ({
      shippedQty: total.shippedQty + load.shipped_qty,
      dispatchCost: total.dispatchCost + Number(load.dispatch_cost),
    }),
    { shippedQty: 0, dispatchCost: 0 },
  );
}

export function getContractorCompletionPercent(issuedQty: number, completedQty: number): number {
  if (issuedQty <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((completedQty / issuedQty) * 100));
}
