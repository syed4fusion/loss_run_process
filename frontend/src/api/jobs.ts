import { apiClient } from "./client";
import type { JobResponse } from "../types";

export async function createJob(files: File[], insuredName?: string): Promise<JobResponse> {
  const formData = new FormData();
  if (insuredName?.trim()) {
    formData.append("insured_name", insuredName.trim());
  }
  for (const file of files) {
    formData.append("files", file);
  }
  const { data } = await apiClient.post<JobResponse>("/api/v1/jobs/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const { data } = await apiClient.get<JobResponse>(`/api/v1/jobs/${jobId}`);
  return data;
}

export async function runJob(jobId: string): Promise<void> {
  await apiClient.post(`/api/v1/jobs/${jobId}/run`);
}
