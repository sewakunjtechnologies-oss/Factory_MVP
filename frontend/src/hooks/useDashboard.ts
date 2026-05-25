import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchAlerts, fetchDashboard, generateAlerts } from "../api/dashboard";

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useGenerateAlerts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: generateAlerts,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useAlerts(activeOnly = true) {
  return useQuery({
    queryKey: ["alerts", activeOnly],
    queryFn: () => fetchAlerts(activeOnly),
    staleTime: 30_000,
  });
}
