import { apiClient } from "./client";
import type { HitlDetailResponse, SummarySections } from "../types";

export async function getHitlDetail(jobId: string): Promise<HitlDetailResponse> {
  const { data } = await apiClient.get<HitlDetailResponse>(`/api/v1/hitl/${jobId}`);
  return data;
}

export async function approveHitl(jobId: string, userId: string): Promise<void> {
  await apiClient.post(`/api/v1/hitl/${jobId}/approve`, { user_id: userId });
}

export async function editHitl(jobId: string, userId: string, sections: SummarySections): Promise<void> {
  await apiClient.post(`/api/v1/hitl/${jobId}/edit`, {
    user_id: userId,
    edited_sections: sections,
  });
}

export async function rejectHitl(jobId: string, userId: string, reason: string): Promise<void> {
  await apiClient.post(`/api/v1/hitl/${jobId}/reject`, {
    user_id: userId,
    reason,
  });
}

