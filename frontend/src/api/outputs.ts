import { apiClient } from "./client";
import type { AnalyticsResult, ClaimsArray, RedFlagReport, SummarySections } from "../types";

export async function getSummary(jobId: string): Promise<SummarySections> {
  const { data } = await apiClient.get<SummarySections>(`/api/v1/outputs/${jobId}/summary`);
  return data;
}

export async function getClaims(jobId: string): Promise<ClaimsArray> {
  const { data } = await apiClient.get<ClaimsArray>(`/api/v1/outputs/${jobId}/claims`);
  return data;
}

export async function getAnalytics(jobId: string): Promise<AnalyticsResult> {
  const { data } = await apiClient.get<AnalyticsResult>(`/api/v1/outputs/${jobId}/analytics`);
  return data;
}

export async function getRedflags(jobId: string): Promise<RedFlagReport> {
  const { data } = await apiClient.get<RedFlagReport>(`/api/v1/outputs/${jobId}/redflags`);
  return data;
}

export function buildPdfUrl(jobId: string): string {
  const base = apiClient.defaults.baseURL ?? "http://localhost:8000";
  return `${base}/api/v1/outputs/${jobId}/pdf`;
}
