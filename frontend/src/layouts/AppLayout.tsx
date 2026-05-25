import {
  Bell,
  Bot,
  ClipboardList,
  Factory,
  Layers,
  LogOut,
  Network,
  PackageCheck,
  PackageSearch,
  RefreshCcw,
  Scissors,
  Sparkles,
  Truck,
  Users,
} from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { NotificationBell } from "../components/NotificationBell";
import { NotificationToaster } from "../components/NotificationToaster";
import { useAuthStore } from "../store/authStore";
import { cn } from "../utils/cn";

type NavGroup = {
  heading: string;
  items: { to: string; label: string; icon: typeof Factory; description?: string }[];
};

// Grouped by the 9-step workflow so the sidebar reads top-to-bottom in the same
// order the owner actually works.
const NAV_GROUPS: NavGroup[] = [
  {
    heading: "Overview",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: Factory, description: "Today at a glance" },
      { to: "/assistant", label: "Ask assistant", icon: Bot, description: "Voice or chat" },
      { to: "/ai-import", label: "AI Excel import", icon: Sparkles, description: "Upload any sheet" },
    ],
  },
  {
    heading: "Orders & inventory",
    items: [
      { to: "/pos", label: "Purchase orders", icon: ClipboardList, description: "Step 1" },
      { to: "/inventory", label: "Fabric & pieces stock", icon: Layers, description: "Step 1–2" },
    ],
  },
  {
    heading: "Fabric",
    items: [
      { to: "/fabric", label: "Fabric receipts", icon: PackageSearch, description: "Step 4" },
      { to: "/fabric-ops", label: "Mill orders & follow-up", icon: RefreshCcw, description: "Step 3" },
    ],
  },
  {
    heading: "Production",
    items: [
      { to: "/allocation", label: "Allocate work", icon: Network, description: "Step 5–6" },
      { to: "/production", label: "Cutting & stitching", icon: Scissors, description: "Step 5–7" },
      { to: "/contractors", label: "Contractors", icon: Users },
    ],
  },
  {
    heading: "Finish",
    items: [
      { to: "/packing", label: "Packing planner", icon: PackageCheck, description: "Step 8" },
      { to: "/dispatch", label: "Dispatch", icon: Truck, description: "Step 9" },
    ],
  },
  {
    heading: "Attention",
    items: [
      { to: "/reminders", label: "Reminders & shortages", icon: Bell },
    ],
  },
];

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

export function AppLayout() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Sidebar: flex column so the nav can scroll independently of the brand header + footer. */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-teal-700 text-white">
            <PackageCheck className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-slate-950">Factory Control</p>
            <p className="truncate text-xs text-slate-500">Execution cockpit</p>
          </div>
        </div>
        {/* `flex-1 min-h-0` lets this region absorb leftover height and scroll. */}
        <nav className="sidebar-scroll flex-1 min-h-0 space-y-3 overflow-y-auto px-3 py-3">
          {NAV_GROUPS.map((group) => (
            <div key={group.heading} className="space-y-0.5">
              <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">{group.heading}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "group relative flex items-center gap-3 rounded-md px-3 py-1.5 text-sm font-semibold transition",
                      isActive
                        ? "bg-teal-50 text-teal-800"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive ? (
                        <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-r-full bg-teal-600" aria-hidden="true" />
                      ) : null}
                      <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 truncate">{item.label}</span>
                      {item.description ? (
                        <span className="ml-auto shrink-0 text-[10px] font-normal text-slate-400">{item.description}</span>
                      ) : null}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        {/* Footer pinned to the bottom — user + logout always reachable. */}
        <div className="shrink-0 border-t border-slate-200 px-3 py-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-1.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700">
              {(user?.full_name ?? "U").slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-slate-950">{user?.full_name ?? "Factory user"}</p>
              <p className="truncate text-[10px] uppercase tracking-wide text-slate-500">{user?.role ?? "owner"}</p>
            </div>
            <button
              type="button"
              className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              onClick={handleLogout}
              aria-label="Logout"
              title="Logout"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <div>
              <p className="text-sm font-semibold text-slate-950">Today’s execution board</p>
              <p className="text-xs text-slate-500">Pending work, risk, and ownership in one pass</p>
            </div>
            <div className="flex items-center gap-3">
              <NotificationBell />
              {/* On desktop the sidebar footer already shows user + logout, so hide them here to remove duplication. */}
              <div className="hidden text-right sm:block lg:hidden">
                <p className="text-sm font-semibold text-slate-950">{user?.full_name ?? "Factory user"}</p>
                <p className="text-xs text-slate-500">{user?.role ?? "owner"}</p>
              </div>
              <button type="button" className="secondary-button lg:hidden" onClick={handleLogout} aria-label="Logout">
                <LogOut className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 px-4 py-2 lg:hidden">
            {ALL_NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold",
                    isActive ? "bg-teal-50 text-teal-800" : "text-slate-600",
                  )
                }
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>
        <main className="px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
      <NotificationToaster />
    </div>
  );
}
