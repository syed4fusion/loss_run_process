import { apiClient } from "./client";
import type { JobResponse } from "../types";

export async function createJob(insuredName: string, files: File[]): Promise<JobResponse> {
  const formData = new FormData();
  formData.append("insured_name", insuredName);
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
