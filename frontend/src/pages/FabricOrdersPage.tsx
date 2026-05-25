import { useMemo, useState, type FormEvent } from "react";
import { Factory, RefreshCcw } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { MillSplitForm } from "../components/MillSplitForm";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import {
  useCreateCuttingAnalysis,
  useCreateFabricMillOrder,
  useCreateMillFollowup,
  useCuttingAnalysis,
  useFabricIssues,
  useFabricMillOrders,
  useIssueFabricToCutting,
  useLateMillOrders,
  useMillFollowupsDue,
  useMillWastageHistory,
  useVerifyFabricReceipt,
} from "../hooks/useOperations";
import { todayISO } from "../utils/forms";
import { formatCurrency, formatDate, formatMeters } from "../utils/format";

export default function FabricOrdersPage() {
  const pos = usePurchaseOrders();
  const poOptions = useMemo(() => (pos.data ?? []).map((po) => [po.id, po.po_number]), [pos.data]);
  const poNumberById = useMemo(() => new Map((pos.data ?? []).map((po) => [po.id, po.po_number])), [pos.data]);
  const [poId, setPoId] = useState("");
  const orders = useFabricMillOrders(poId || undefined);
  const lateOrders = useLateMillOrders();
  const dueFollowups = useMillFollowupsDue();
  const issues = useFabricIssues(poId || undefined);
  const analysis = useCuttingAnalysis(poId || undefined);
  const wastageHistory = useMillWastageHistory();

  const createOrder = useCreateFabricMillOrder();
  const createFollowup = useCreateMillFollowup();
  const verifyReceipt = useVerifyFabricReceipt();
  const issueFabric = useIssueFabricToCutting();
  const createAnalysis = useCreateCuttingAnalysis();

  const [orderForm, setOrderForm] = useState({ mill_name: "", ordered_meters: "", committed_delivery_date: todayISO() });
  const [followupForm, setFollowupForm] = useState({ mill_order_id: "", followup_date: todayISO(), next_followup_date: "", response_notes: "" });
  const [verifyForm, setVerifyForm] = useState({ receipt_id: "", verification_status: "approved", action_taken: "accept", verification_date: todayISO(), mismatch_reason: "" });
  const [issueForm, setIssueForm] = useState({ issued_meters: "", issue_date: todayISO(), fabric_receipt_id: "", remarks: "" });
  const [analysisForm, setAnalysisForm] = useState({
    planned_consumption_m: "",
    actual_consumption_m: "",
    planned_wastage_m: "",
    actual_wastage_m: "",
    reason_for_difference: "",
    mill_name: "",
  });
  const millNamesForSelectedPO = useMemo(() => {
    const names = new Set<string>();
    for (const order of orders.data ?? []) {
      if (order.mill_name) names.add(order.mill_name);
    }
    return Array.from(names).sort();
  }, [orders.data]);

  function submitOrder(event: FormEvent) {
    event.preventDefault();
    if (!poId) return;
    createOrder.mutate({
      purchase_order_id: poId,
      mill_name: orderForm.mill_name,
      ordered_meters: Number(orderForm.ordered_meters),
      committed_delivery_date: orderForm.committed_delivery_date,
    });
  }

  function submitFollowup(event: FormEvent) {
    event.preventDefault();
    createFollowup.mutate({
      mill_order_id: followupForm.mill_order_id,
      followup_date: followupForm.followup_date,
      next_followup_date: followupForm.next_followup_date || null,
      response_notes: followupForm.response_notes || null,
    });
  }

  function submitVerify(event: FormEvent) {
    event.preventDefault();
    verifyReceipt.mutate({
      receipt_id: verifyForm.receipt_id,
      verification_status: verifyForm.verification_status as "pending" | "approved" | "mismatch" | "rejected" | "returned",
      action_taken: verifyForm.action_taken as "accept" | "return_to_supplier" | "reopen_shortage" | "adjust_consumption" | "hold",
      verification_date: verifyForm.verification_date,
      mismatch_reason: verifyForm.mismatch_reason || null,
    });
  }

  function submitIssue(event: FormEvent) {
    event.preventDefault();
    if (!poId) return;
    issueFabric.mutate({
      purchase_order_id: poId,
      issued_meters: Number(issueForm.issued_meters),
      issue_date: issueForm.issue_date,
      fabric_receipt_id: issueForm.fabric_receipt_id || null,
      remarks: issueForm.remarks || null,
    });
  }

  function submitAnalysis(event: FormEvent) {
    event.preventDefault();
    if (!poId) return;
    createAnalysis.mutate({
      purchase_order_id: poId,
      planned_consumption_m: Number(analysisForm.planned_consumption_m),
      actual_consumption_m: Number(analysisForm.actual_consumption_m),
      planned_wastage_m: Number(analysisForm.planned_wastage_m),
      actual_wastage_m: Number(analysisForm.actual_wastage_m),
      reason_for_difference: analysisForm.reason_for_difference || null,
      mill_name: analysisForm.mill_name || null,
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-950">Fabric Order & Verification</h1>
          <p className="mt-1 text-sm text-slate-500">Track mill orders, follow-up, verification, issue to cutting, and wastage.</p>
        </div>
        <select className="field max-w-56" value={poId} onChange={(event) => setPoId(event.target.value)}>
          <option value="">Select PO</option>
          {poOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>

      {poId ? <MillSplitForm purchaseOrderId={poId} /> : null}

      <section className="grid gap-4 xl:grid-cols-2">
        <form className="panel p-4" onSubmit={submitOrder}>
          <h2 className="text-sm font-semibold text-slate-950">Create Mill Order</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <input className="field" placeholder="Mill name" value={orderForm.mill_name} onChange={(event) => setOrderForm({ ...orderForm, mill_name: event.target.value })} required />
            <input className="field" placeholder="Ordered meters" type="number" min={1} value={orderForm.ordered_meters} onChange={(event) => setOrderForm({ ...orderForm, ordered_meters: event.target.value })} required />
            <input className="field sm:col-span-2" type="date" value={orderForm.committed_delivery_date} onChange={(event) => setOrderForm({ ...orderForm, committed_delivery_date: event.target.value })} required />
          </div>
          <button className="primary-button mt-3 w-full" disabled={createOrder.isPending || !poId}><Factory className="h-4 w-4" />Create Order</button>
          {createOrder.isError ? <p className="mt-2 text-sm text-red-700">{getApiErrorMessage(createOrder.error)}</p> : null}
        </form>

        <form className="panel p-4" onSubmit={submitFollowup}>
          <h2 className="text-sm font-semibold text-slate-950">Mill Follow-up</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <select className="field sm:col-span-2" value={followupForm.mill_order_id} onChange={(event) => setFollowupForm({ ...followupForm, mill_order_id: event.target.value })} required>
              <option value="">Select mill order</option>
              {(orders.data ?? []).map((order) => <option key={order.id} value={order.id}>{order.mill_name}</option>)}
            </select>
            <input className="field" type="date" value={followupForm.followup_date} onChange={(event) => setFollowupForm({ ...followupForm, followup_date: event.target.value })} required />
            <input className="field" type="date" value={followupForm.next_followup_date} onChange={(event) => setFollowupForm({ ...followupForm, next_followup_date: event.target.value })} />
            <input className="field sm:col-span-2" placeholder="Response notes" value={followupForm.response_notes} onChange={(event) => setFollowupForm({ ...followupForm, response_notes: event.target.value })} />
          </div>
          <button className="secondary-button mt-3 w-full" disabled={createFollowup.isPending}><RefreshCcw className="h-4 w-4" />Record Follow-up</button>
        </form>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex flex-col gap-1 border-b border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-950">Mill Invoices / Orders</h2>
            <p className="text-xs text-slate-500">Use this table in the owner demo to show shortage orders and invoice value.</p>
          </div>
          <p className="text-xs font-medium text-slate-500">{(orders.data ?? []).length} order(s)</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Invoice #</th>
                <th className="px-4 py-3">PO</th>
                <th className="px-4 py-3">Mill</th>
                <th className="px-4 py-3">Meters</th>
                <th className="px-4 py-3">Rate</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Delivery</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {(orders.data ?? []).map((order) => {
                const rate = Number(order.ordered_rate_per_meter ?? 0);
                const amount = Number(order.ordered_meters) * rate;
                const orderStatus = order.status ?? "ordered";
                const status = orderStatus === "ordered" ? "Pending Delivery" : orderStatus.replaceAll("_", " ");
                return (
                  <tr key={order.id}>
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-700">{order.invoice_number ?? "—"}</td>
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-950">{poNumberById.get(order.purchase_order_id) ?? "Selected PO"}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{order.mill_name}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatMeters(order.ordered_meters)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatCurrency(rate)}</td>
                    <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-950">{formatCurrency(amount)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatDate(order.committed_delivery_date)}</td>
                    <td className="whitespace-nowrap px-4 py-3 capitalize text-slate-700">{status}</td>
                  </tr>
                );
              })}
              {(orders.data ?? []).length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={8}>No mill invoice/order is available for the current selection.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <form className="panel p-4" onSubmit={submitVerify}>
          <h2 className="text-sm font-semibold text-slate-950">Fabric Verification</h2>
          <div className="mt-3 space-y-2">
            <input className="field" placeholder="Receipt ID" value={verifyForm.receipt_id} onChange={(event) => setVerifyForm({ ...verifyForm, receipt_id: event.target.value })} required />
            <select className="field" value={verifyForm.verification_status} onChange={(event) => setVerifyForm({ ...verifyForm, verification_status: event.target.value })}>
              <option value="approved">Approved</option><option value="mismatch">Mismatch</option><option value="rejected">Rejected</option><option value="pending">Pending</option>
            </select>
            <select className="field" value={verifyForm.action_taken} onChange={(event) => setVerifyForm({ ...verifyForm, action_taken: event.target.value })}>
              <option value="accept">Accept</option><option value="return_to_supplier">Return to Supplier</option><option value="reopen_shortage">Reopen Shortage</option><option value="hold">Hold</option>
            </select>
            <input className="field" type="date" value={verifyForm.verification_date} onChange={(event) => setVerifyForm({ ...verifyForm, verification_date: event.target.value })} />
          </div>
          <button className="secondary-button mt-3 w-full" disabled={verifyReceipt.isPending}>Save Verification</button>
        </form>

        <form className="panel p-4" onSubmit={submitIssue}>
          <h2 className="text-sm font-semibold text-slate-950">Issue To Cutting</h2>
          <div className="mt-3 space-y-2">
            <input className="field" placeholder="Issued meters" type="number" min={1} value={issueForm.issued_meters} onChange={(event) => setIssueForm({ ...issueForm, issued_meters: event.target.value })} required />
            <input className="field" placeholder="Receipt ID (optional)" value={issueForm.fabric_receipt_id} onChange={(event) => setIssueForm({ ...issueForm, fabric_receipt_id: event.target.value })} />
            <input className="field" type="date" value={issueForm.issue_date} onChange={(event) => setIssueForm({ ...issueForm, issue_date: event.target.value })} required />
            <input className="field" placeholder="Remarks" value={issueForm.remarks} onChange={(event) => setIssueForm({ ...issueForm, remarks: event.target.value })} />
          </div>
          <button className="secondary-button mt-3 w-full" disabled={issueFabric.isPending || !poId}>Issue Fabric</button>
        </form>

        <form className="panel p-4" onSubmit={submitAnalysis}>
          <h2 className="text-sm font-semibold text-slate-950">Cutting Wastage</h2>
          <div className="mt-3 grid gap-2">
            {millNamesForSelectedPO.length > 0 ? (
              <select
                className="field"
                value={analysisForm.mill_name}
                onChange={(event) => setAnalysisForm({ ...analysisForm, mill_name: event.target.value })}
              >
                <option value="">Mill (optional — attributes wastage)</option>
                {millNamesForSelectedPO.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            ) : (
              <input
                className="field"
                placeholder="Mill name (optional — attributes wastage)"
                value={analysisForm.mill_name}
                onChange={(event) => setAnalysisForm({ ...analysisForm, mill_name: event.target.value })}
              />
            )}
            <input className="field" placeholder="Planned consumption" type="number" min={0} value={analysisForm.planned_consumption_m} onChange={(event) => setAnalysisForm({ ...analysisForm, planned_consumption_m: event.target.value })} required />
            <input className="field" placeholder="Actual consumption" type="number" min={0} value={analysisForm.actual_consumption_m} onChange={(event) => setAnalysisForm({ ...analysisForm, actual_consumption_m: event.target.value })} required />
            <input className="field" placeholder="Planned wastage" type="number" min={0} value={analysisForm.planned_wastage_m} onChange={(event) => setAnalysisForm({ ...analysisForm, planned_wastage_m: event.target.value })} required />
            <input className="field" placeholder="Actual wastage" type="number" min={0} value={analysisForm.actual_wastage_m} onChange={(event) => setAnalysisForm({ ...analysisForm, actual_wastage_m: event.target.value })} required />
          </div>
          <button className="secondary-button mt-3 w-full" disabled={createAnalysis.isPending || !poId}>Save Analysis</button>
        </form>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex flex-col gap-1 border-b border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-950">Mill Wastage History</h2>
            <p className="text-xs text-slate-500">Average wastage delta per mill across all POs — the owner's "which mill is risky" memory.</p>
          </div>
          <p className="text-xs font-medium text-slate-500">{(wastageHistory.data ?? []).length} mill(s)</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Mill</th>
                <th className="px-4 py-3">Events</th>
                <th className="px-4 py-3">Total Planned</th>
                <th className="px-4 py-3">Total Actual</th>
                <th className="px-4 py-3">Avg Delta</th>
                <th className="px-4 py-3">Flag</th>
                <th className="px-4 py-3">Last Recorded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {(wastageHistory.data ?? []).map((entry) => {
                const flagColor =
                  entry.flag === "high"
                    ? "bg-red-100 text-red-800"
                    : entry.flag === "low"
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-slate-100 text-slate-700";
                return (
                  <tr key={entry.mill_name}>
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-950">{entry.mill_name}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{entry.event_count}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatMeters(entry.total_planned_wastage_m)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatMeters(entry.total_actual_wastage_m)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatMeters(entry.avg_difference_m)}</td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${flagColor}`}>{entry.flag}</span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{entry.last_recorded_at ? formatDate(entry.last_recorded_at) : "—"}</td>
                  </tr>
                );
              })}
              {(wastageHistory.data ?? []).length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={7}>
                    No mill wastage recorded yet. Attribute a mill on the Cutting Wastage form to start building this history.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="panel overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-950">Late Mills</div>
          <div className="divide-y divide-slate-100">
            {(lateOrders.data ?? []).map((order) => (
              <div key={order.id} className="px-4 py-3 text-sm">
                <p className="font-semibold text-red-700">{order.mill_name}</p>
                <p className="text-slate-600">{formatDate(order.committed_delivery_date)} · {formatMeters(order.ordered_meters)}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="panel overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-950">Current PO: Issue & Wastage Snapshot</div>
          <div className="px-4 py-3 text-sm text-slate-700">
            <p>Issued to cutting: {formatMeters((issues.data ?? []).reduce((sum, item) => sum + Number(item.issued_meters), 0))}</p>
            {(analysis.data ?? []).slice(0, 1).map((row) => (
              <p key={row.id} className="mt-1">Wastage difference: {formatMeters(row.wastage_difference_m)}</p>
            ))}
            {(dueFollowups.data ?? []).length > 0 ? <p className="mt-2 text-amber-700">Due follow-ups: {(dueFollowups.data ?? []).length}</p> : null}
          </div>
        </div>
      </section>
    </div>
  );
}
