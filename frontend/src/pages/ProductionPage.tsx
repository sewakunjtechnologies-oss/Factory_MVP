import { type Dispatch, type FormEvent, type SetStateAction, useMemo, useState } from "react";
import { CheckCircle2, ClipboardList, Send } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { LoadingState } from "../components/LoadingState";
import { useContractors } from "../hooks/useContractors";
import { useAllocations, useSubmitStageProgress } from "../hooks/useProduction";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import type { StageName } from "../types/api";
import type { ProductionFormValues } from "../types/forms";
import { productionStages } from "../utils/factoryMetrics";
import { buildProductionPayload } from "../utils/forms";
import { formatNumber, stageShortName } from "../utils/format";

const emptyForm: ProductionFormValues = {
  purchase_order_id: "",
  stage: "cutting",
  allocation_id: "",
  completed_today: "0",
  approved_today: "0",
  rejected_today: "0",
  repair_today: "0",
  alter_today: "0",
  moved_to_next_stage_today: "0",
  delay_days: "0",
  remarks: "",
};

export default function ProductionPage() {
  const purchaseOrdersQuery = usePurchaseOrders();
  const contractorsQuery = useContractors();
  const [values, setValues] = useState<ProductionFormValues>(emptyForm);
  const allocationsQuery = useAllocations(values.purchase_order_id || undefined);
  const submitMutation = useSubmitStageProgress();

  const selectedPO = purchaseOrdersQuery.data?.find((po) => po.id === values.purchase_order_id);
  const contractorNameById = useMemo(
    () => new Map((contractorsQuery.data ?? []).map((contractor) => [contractor.id, contractor.name])),
    [contractorsQuery.data],
  );
  const stageSummaryById = useMemo(
    () => new Map((selectedPO?.stage_summaries ?? []).map((stage) => [stage.id, stage])),
    [selectedPO],
  );
  const filteredAllocations = (allocationsQuery.data ?? []).filter((allocation) => {
    const stage = stageSummaryById.get(allocation.stage_summary_id);
    return stage?.stage === values.stage;
  });
  const selectedStage = selectedPO?.stage_summaries.find((stage) => stage.stage === values.stage);
  const selectedAllocation = filteredAllocations.find((allocation) => allocation.id === values.allocation_id);
  const moveAvailable = selectedStage ? Math.max(selectedStage.approved_qty - selectedStage.moved_to_next_qty, 0) : 0;
  const completedToday = toNumber(values.completed_today);
  const approvedToday = toNumber(values.approved_today);
  const rejectedToday = toNumber(values.rejected_today);
  const repairToday = toNumber(values.repair_today);
  const alterToday = toNumber(values.alter_today);
  const movedToday = toNumber(values.moved_to_next_stage_today);
  const delayDays = toNumber(values.delay_days);
  const outcomeTotal = approvedToday + rejectedToday + repairToday + alterToday;
  const entryErrors = getEntryErrors({
    pendingQty: selectedStage?.pending_qty ?? 0,
    allocationRemaining: selectedAllocation ? selectedAllocation.issued_qty - selectedAllocation.completed_qty : null,
    completedToday,
    outcomeTotal,
    movedToday,
    moveAvailable,
    delayDays,
  });

  if (purchaseOrdersQuery.isLoading) {
    return <LoadingState label="Loading production entry" />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitMutation.mutate(buildProductionPayload(values), {
      onSuccess: () => setValues((current) => ({ ...emptyForm, purchase_order_id: current.purchase_order_id, stage: current.stage })),
    });
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,560px)_1fr]">
      <section className="panel p-5">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-teal-700" aria-hidden="true" />
          <div>
            <h1 className="text-xl font-bold text-slate-950">Production Entry</h1>
            <p className="text-sm text-slate-500">Record completed, approved, failed, and moved quantities.</p>
          </div>
        </div>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="label" htmlFor="purchase_order_id">
                Purchase Order
              </label>
              <select
                id="purchase_order_id"
                className="field"
                value={values.purchase_order_id}
                onChange={(event) => setValues((current) => ({ ...current, purchase_order_id: event.target.value, allocation_id: "" }))}
                required
              >
                <option value="">Select PO</option>
                {(purchaseOrdersQuery.data ?? []).map((po) => (
                  <option key={po.id} value={po.id}>
                    {po.po_number}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="label" htmlFor="stage">
                Stage
              </label>
              <select
                id="stage"
                className="field"
                value={values.stage}
                onChange={(event) => setValues((current) => ({ ...current, stage: event.target.value as StageName, allocation_id: "" }))}
              >
                {productionStages.map((stage) => (
                  <option key={stage} value={stage}>
                    {stageShortName(stage)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <label className="label" htmlFor="allocation_id">
              Contractor
            </label>
            <select
              id="allocation_id"
              className="field"
              value={values.allocation_id}
              onChange={(event) => setValues((current) => ({ ...current, allocation_id: event.target.value }))}
            >
              <option value="">No contractor allocation</option>
              {filteredAllocations.map((allocation) => (
                <option key={allocation.id} value={allocation.id}>
                  {contractorNameById.get(allocation.contractor_id) ?? "Contractor"} · issued {formatNumber(allocation.issued_qty)}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <NumberField id="completed_today" label="Completed" values={values} setValues={setValues} max={selectedStage?.pending_qty} />
            <NumberField id="approved_today" label="Approved" values={values} setValues={setValues} max={completedToday || undefined} />
            <NumberField id="rejected_today" label="Rejected" values={values} setValues={setValues} max={completedToday || undefined} />
            <NumberField id="repair_today" label="Repair" values={values} setValues={setValues} max={completedToday || undefined} />
            <NumberField id="alter_today" label="Alter" values={values} setValues={setValues} max={completedToday || undefined} />
            <NumberField id="moved_to_next_stage_today" label="Move Next" values={values} setValues={setValues} max={moveAvailable} />
            <NumberField id="delay_days" label="Delay Days" values={values} setValues={setValues} />
          </div>

          <div className="space-y-2">
            <label className="label" htmlFor="remarks">
              Remarks
            </label>
            <textarea
              id="remarks"
              className="field min-h-24 py-2"
              value={values.remarks}
              onChange={(event) => setValues((current) => ({ ...current, remarks: event.target.value }))}
            />
          </div>

          {submitMutation.isError ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {getApiErrorMessage(submitMutation.error)}
            </div>
          ) : null}
          {entryErrors.length > 0 ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {entryErrors[0]}
            </div>
          ) : null}
          {submitMutation.isSuccess ? (
            <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Production entry saved.
            </div>
          ) : null}

          <button type="submit" className="primary-button w-full" disabled={submitMutation.isPending || entryErrors.length > 0}>
            <Send className="h-4 w-4" aria-hidden="true" />
            {submitMutation.isPending ? "Submitting" : "Submit Production"}
          </button>
        </form>
      </section>

      <section className="panel p-5">
        <h2 className="text-sm font-semibold text-slate-950">Selected PO Snapshot</h2>
        {!selectedPO ? (
          <p className="mt-4 text-sm text-slate-500">Select a PO to see live stage quantities before submitting.</p>
        ) : (
          <div className="mt-4 grid gap-3">
            {selectedPO.stage_summaries
              .filter((stage) => productionStages.includes(stage.stage))
              .map((stage) => (
                <div key={stage.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-slate-950">{stageShortName(stage.stage)}</p>
                    <p className="text-xs text-slate-500">
                      Pending {formatNumber(stage.pending_qty)} · Move cap {formatNumber(Math.max(stage.approved_qty - stage.moved_to_next_qty, 0))}
                    </p>
                  </div>
                  <div className="mt-3 grid grid-cols-4 gap-3 text-xs">
                    <Metric label="Completed" value={stage.completed_qty} />
                    <Metric label="Approved" value={stage.approved_qty} />
                    <Metric label="Rejected" value={stage.rejected_qty} />
                    <Metric label="Repair" value={stage.repair_qty + stage.alter_qty} />
                  </div>
                </div>
              ))}
          </div>
        )}
      </section>
    </div>
  );
}

type NumericKey = keyof Pick<
  ProductionFormValues,
  "completed_today" | "approved_today" | "rejected_today" | "repair_today" | "alter_today" | "moved_to_next_stage_today" | "delay_days"
>;

function NumberField({
  id,
  label,
  values,
  setValues,
  max,
}: {
  id: NumericKey;
  label: string;
  values: ProductionFormValues;
  setValues: Dispatch<SetStateAction<ProductionFormValues>>;
  max?: number;
}) {
  return (
    <div className="space-y-2">
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="field"
        type="number"
        min="0"
        max={max}
        value={values[id]}
        onChange={(event) => setValues((current) => ({ ...current, [id]: event.target.value }))}
      />
    </div>
  );
}

function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getEntryErrors({
  pendingQty,
  allocationRemaining,
  completedToday,
  outcomeTotal,
  movedToday,
  moveAvailable,
  delayDays,
}: {
  pendingQty: number;
  allocationRemaining: number | null;
  completedToday: number;
  outcomeTotal: number;
  movedToday: number;
  moveAvailable: number;
  delayDays: number;
}): string[] {
  const errors: string[] = [];
  if (completedToday > pendingQty) {
    errors.push("Completed quantity cannot exceed stage pending quantity.");
  }
  if (allocationRemaining !== null && completedToday > allocationRemaining) {
    errors.push("Completed quantity cannot exceed remaining contractor allocation.");
  }
  if (completedToday === 0 && outcomeTotal > 0) {
    errors.push("Completed quantity is required when recording approved or failed quantities.");
  }
  if (completedToday > 0 && outcomeTotal !== completedToday) {
    errors.push("Completed must equal approved plus rejected, repair, and alter quantities.");
  }
  if (movedToday > moveAvailable) {
    errors.push("Move next cannot exceed approved quantity not yet moved.");
  }
  if (completedToday === 0 && movedToday === 0 && delayDays === 0) {
    errors.push("Enter production, movement, or delay before submitting.");
  }
  return errors;
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-slate-500">{label}</p>
      <p className="mt-1 font-semibold text-slate-950">{formatNumber(value)}</p>
    </div>
  );
}
