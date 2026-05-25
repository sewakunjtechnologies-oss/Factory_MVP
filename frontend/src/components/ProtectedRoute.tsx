import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuthStore } from "../store/authStore";
import { canAccessRoute, getHomeForRole } from "../utils/roleAccess";

export function ProtectedRoute() {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!canAccessRoute(user?.role, location.pathname)) {
    return <Navigate to={getHomeForRole(user?.role)} replace />;
  }

  return <Outlet />;
}
