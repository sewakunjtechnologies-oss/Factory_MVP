import { useQuery } from "@tanstack/react-query";

import { fetchContractors } from "../api/contractors";

export function useContractors() {
  return useQuery({
    queryKey: ["contractors"],
    queryFn: fetchContractors,
    staleTime: 60_000,
  });
}
