import { Bell, Bot, Home, ListChecks, LogOut, PlusCircle } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuthStore } from "../store/authStore";
import { cn } from "../utils/cn";

const NAV = [
  { to: "/mobile/home", label: "Home", icon: Home },
  { to: "/mobile/pos", label: "POs", icon: ListChecks },
  { to: "/mobile/po/create", label: "Add PO", icon: PlusCircle },
  { to: "/mobile/assistant", label: "AI", icon: Bot },
  { to: "/mobile/alerts", label: "Alerts", icon: Bell },
];

export function MobileLayout() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  return (
    <div className="min-h-[100dvh] bg-slate-50 pb-[calc(env(safe-area-inset-bottom)+4.75rem)]">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-lg font-bold text-slate-950">Factory Control</p>
            <p className="text-xs text-slate-500">Phone workflow for {user?.full_name ?? "owner"}</p>
          </div>
          <button
            type="button"
            className="flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600"
            onClick={() => {
              logout();
              navigate("/login", { replace: true });
            }}
            aria-label="Logout"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </header>
      <main className="px-3 py-4">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 px-2 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-2 backdrop-blur">
        <div className="grid grid-cols-5 gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex min-h-14 flex-col items-center justify-center gap-1 rounded-xl text-[11px] font-semibold",
                  isActive ? "bg-teal-50 text-teal-800" : "text-slate-500",
                )
              }
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
