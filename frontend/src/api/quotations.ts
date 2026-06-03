import { api } from "./axios";

export async function fetchQuotationPdfBlob(poNumber: string): Promise<Blob> {
  const response = await api.get<Blob>(`/quotations/${encodeURIComponent(poNumber)}/pdf`, {
    responseType: "blob",
  });
  return response.data;
}
