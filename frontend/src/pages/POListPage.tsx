import { Link } from "react-router-dom";
import { Plus, Search } from "lucide-react";

import { LoadingState } from "../components/LoadingState";
import { ProgressBar } from "../components/ProgressBar";
import { StatusBadge } from "../components/StatusBadge";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import { getBottleneckStage, getPOCompletedQty, getPOPendingQty } from "../utils/factoryMetrics";
import { formatDate, formatNumber, stageShortName } from "../utils/format";

export default function POListPage() {
  const purchaseOrdersQuery = usePurchaseOrders();

  if (purchaseOrdersQuery.isLoading) {
    return <LoadingState label="Loading purchase orders" />;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-950">Purchase Orders</h1>
          <p className="mt-1 text-sm text-slate-500">PO-driven execution status from fabric through dispatch.</p>
        </div>
        <Link to="/pos/create" className="primary-button">
          <Plus className="h-4 w-4" aria-hidden="true" />
          Create PO
        </Link>
      </div>

      <section className="panel overflow-hidden">
        <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
          <Search className="h-4 w-4 text-teal-700" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-slate-950">Live PO Board</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">PO</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Qty</th>
                <th className="px-4 py-3">Progress</th>
                <th className="px-4 py-3">Pending</th>
                <th className="px-4 py-3">Bottleneck</th>
                <th className="px-4 py-3">Promise</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(purchaseOrdersQuery.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-sm text-slate-500">
                    No purchase orders yet. Create one to get started.
                  </td>
                </tr>
              ) : null}
              {(purchaseOrdersQuery.data ?? []).map((po) => {
                const completed = getPOCompletedQty(po);
                const pending = getPOPendingQty(po);
                const bottleneck = getBottleneckStage(po);
                return (
                  <tr key={po.id} className="align-middle hover:bg-slate-50">
                    <td className="whitespace-nowrap px-4 py-3 font-semibold text-teal-800">
                      <Link to={`/po/${po.id}`} className="hover:underline">{po.po_number}</Link>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{po.product?.product_name ?? "—"}</td>
                    <td className="num-cell px-4 py-3 text-slate-700">{formatNumber(po.order_quantity_pcs)}</td>
                    <td className="min-w-[8rem] px-4 py-3">
                      <ProgressBar value={po.order_quantity_pcs ? Math.round((completed / po.order_quantity_pcs) * 100) : 0} tone="green" />
                    </td>
                    <td className="num-cell px-4 py-3 font-semibold text-slate-950">{formatNumber(pending)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{bottleneck ? stageShortName(bottleneck.stage) : "—"}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatDate(po.promise_delivery_date)}</td>
                    <td className="whitespace-nowrap px-4 py-3"><StatusBadge value={po.status} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
