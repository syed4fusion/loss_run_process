export type JobStatus = "pending" | "running" | "hitl_pending" | "completed" | "failed";

export type JobFile = {
  id: string;
  filename: string;
  carrier_code: string | null;
  lob_code: string | null;
  policy_period_start: string | null;
  policy_period_end: string | null;
  extraction_status: string;
};

export type JobResponse = {
  id: string;
  insured_name: string;
  status: JobStatus;
  current_stage: string | null;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  files: JobFile[];
};
