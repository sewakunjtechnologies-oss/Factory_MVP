import { api } from "./axios";
import type { ContractorRead } from "../types/api";

export async function fetchContractors(): Promise<ContractorRead[]> {
  const response = await api.get<ContractorRead[]>("/contractors");
  return response.data;
}
