import type { UserRole } from "../types/api";

const roleHome: Record<UserRole, string> = {
  owner: "/dashboard",
  manager: "/dashboard",
};

const allowedRoutes: Record<UserRole, string[]> = {
  owner: ["*"],
  manager: ["*"],
};

export function getHomeForRole(role: UserRole | undefined) {
  return role ? roleHome[role] : "/dashboard";
}

export function canAccessRoute(role: UserRole | undefined, pathname: string) {
  if (!role) return false;
  const allowed = allowedRoutes[role];
  return allowed.includes("*") || allowed.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export function isOwner(role: UserRole | undefined) {
  return role === "owner";
}
