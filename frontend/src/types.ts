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

export type SummarySections = {
  executive_summary: string;
  year_by_year: string;
  large_loss_detail: string;
  open_claim_status: string;
  red_flag_disclosure: string;
  risk_management_observations: string;
  disclaimer?: string;
};

export type ClaimRecord = {
  claim_id: string;
  carrier_code: string;
  lob: string;
  policy_period: string;
  occurrence_date: string | null;
  close_date: string | null;
  status: string;
  claim_type: string;
  description: string;
  amount_paid: string;
  amount_reserved: string;
  amount_incurred: string;
  earned_premium?: string | null;
  subrogation_potential?: boolean;
  litigation_flag?: boolean;
};

export type ClaimsPolicyPeriod = {
  carrier_code: string;
  lob: string;
  period: string;
  earned_premium: string | null;
  claims: ClaimRecord[];
};

export type ClaimsArray = {
  job_id: string;
  insured_name: string;
  policy_periods: ClaimsPolicyPeriod[];
  extraction_notes: string[];
};

export type YearlyStats = {
  year: number;
  claim_count: number;
  total_incurred: number;
  total_paid: number;
  total_reserved: number;
  earned_premium: number;
  loss_ratio: number | null;
  loss_frequency: number | null;
  loss_severity: number;
  large_loss_count: number;
  open_claim_count: number;
};

export type AnalyticsResult = {
  job_id: string;
  yearly_stats: YearlyStats[];
  overall_loss_ratio: number | null;
  frequency_trend: number | null;
  severity_trend: number | null;
  avg_days_to_close: number | null;
  total_open_reserves: number;
  large_loss_ratio: number | null;
  years_analyzed: number[];
  missing_years: number[];
};

export type RedFlag = {
  flag_id?: string;
  flag_type?: string;
  severity?: string;
  narrative?: string;
  rule_description?: string;
  triggered_by?: string;
};

export type RedFlagReport = {
  flags?: RedFlag[];
  critical_count?: number;
  warning_count?: number;
  info_count?: number;
};

export type HitlDetailResponse = {
  job_id: string;
  insured_name: string;
  status: JobStatus;
  draft_summary: SummarySections;
  red_flags: RedFlagReport;
  claims: ClaimsArray;
  analytics: AnalyticsResult;
};

export type ReviewSnapshot = {
  claims: ClaimsArray;
  summary: SummarySections;
  updated_at: string;
};
