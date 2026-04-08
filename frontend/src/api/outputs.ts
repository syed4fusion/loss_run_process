import { apiClient } from "./client";

export async function getSummary(jobId: string): Promise<unknown> {
  const { data } = await apiClient.get(`/api/v1/outputs/${jobId}/summary`);
  return data;
}

export function buildPdfUrl(jobId: string): string {
  const base = apiClient.defaults.baseURL ?? "http://localhost:8000";
  return `${base}/api/v1/outputs/${jobId}/pdf`;
}
