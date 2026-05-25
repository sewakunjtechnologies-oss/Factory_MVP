import { Users } from "lucide-react";

import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { useContractors } from "../hooks/useContractors";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import { titleCase } from "../utils/format";

export default function ContractorsPage() {
  const contractorsQuery = useContractors();
  const purchaseOrdersQuery = usePurchaseOrders();

  if (contractorsQuery.isLoading) {
    return <LoadingState label="Loading contractors" />;
  }

  const contractors = contractorsQuery.data ?? [];
  const activePOs = purchaseOrdersQuery.data?.filter((po) => !["completed", "cancelled"].includes(po.status)).length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-950">Contractors</h1>
        <p className="mt-1 text-sm text-slate-500">Contractor roster and workload context across active POs.</p>
      </div>

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="panel p-4">
          <p className="label">Active Contractors</p>
          <p className="mt-2 text-2xl font-bold text-slate-950">{contractors.filter((contractor) => contractor.is_active).length}</p>
        </div>
        <div className="panel p-4">
          <p className="label">Active POs</p>
          <p className="mt-2 text-2xl font-bold text-slate-950">{activePOs}</p>
        </div>
        <div className="panel p-4">
          <p className="label">Stage Types</p>
          <p className="mt-2 text-2xl font-bold text-slate-950">{new Set(contractors.map((contractor) => contractor.contractor_type)).size}</p>
        </div>
      </section>

      {contractors.length === 0 ? (
        <EmptyState icon={Users} title="No contractors yet" message="Create contractors through the API, then use this page to monitor execution responsibility." />
      ) : (
        <section className="panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Phone</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {contractors.map((contractor) => (
                  <tr key={contractor.id}>
                    <td className="px-4 py-3 font-semibold text-slate-950">{contractor.name}</td>
                    <td className="px-4 py-3 text-slate-600">{titleCase(contractor.contractor_type)}</td>
                    <td className="px-4 py-3 text-slate-600">{contractor.phone ?? "-"}</td>
                    <td className="px-4 py-3 text-slate-600">{contractor.email ?? "-"}</td>
                    <td className="px-4 py-3">
                      <span className={contractor.is_active ? "font-semibold text-emerald-700" : "font-semibold text-slate-500"}>
                        {contractor.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
