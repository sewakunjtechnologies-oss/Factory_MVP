import { api } from "./axios";
import type { AlertRead, OwnerDashboardRead } from "../types/api";

export async function fetchDashboard(): Promise<OwnerDashboardRead> {
  const response = await api.get<OwnerDashboardRead>("/dashboard/owner");
  return response.data;
}

export async function fetchAlerts(activeOnly = true): Promise<AlertRead[]> {
  const response = await api.get<AlertRead[]>("/alerts", {
    params: { active_only: activeOnly },
  });
  return response.data;
}

export async function generateAlerts(): Promise<AlertRead[]> {
  const response = await api.post<AlertRead[]>("/alerts/generate");
  return response.data;
}
