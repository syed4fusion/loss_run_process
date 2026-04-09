import { apiClient } from "./api/client";
import type { ClaimRecord, ClaimsArray, JobResponse, JobStatus, ReviewSnapshot, SummarySections } from "./types";

export const EMPTY_SUMMARY: SummarySections = {
  executive_summary: "",
  year_by_year: "",
  large_loss_detail: "",
  open_claim_status: "",
  red_flag_disclosure: "",
  risk_management_observations: "",
  disclaimer: "",
};

export const STAGE_LABELS: Record<string, string> = {
  pending: "Preparing job",
  ingest: "Validating uploads",
  extract: "Extracting claims",
  normalize: "Structuring extracted claims",
  analytics: "Calculating loss analytics",
  redflags: "Assembling red flags",
  summary: "Preparing the review package",
  hitl_pending: "Ready for review",
  hitl_resume: "Finalizing approved review",
  deliver: "Building the final report",
  completed: "Completed",
  failed: "Failed",
};

export function flattenClaims(claimsArray?: ClaimsArray | null): ClaimRecord[] {
  return (claimsArray?.policy_periods ?? []).flatMap((period) => period.claims ?? []);
}

export function formatCurrency(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) {
    return "N/A";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(parsed);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "N/A";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatFlagType(flagType?: string): string {
  if (!flagType) {
    return "Flag";
  }
  return flagType.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function formatYearSpan(years: number[]): string {
  if (years.length === 0) {
    return "N/A";
  }
  if (years.length === 1) {
    return String(years[0]);
  }
  return `${Math.min(...years)}-${Math.max(...years)}`;
}

export function getCurrentStageLabel(job: JobResponse | null): string {
  if (!job) {
    return "Loading";
  }
  return STAGE_LABELS[job.current_stage ?? job.status] ?? job.current_stage ?? "Processing";
}

export function getWorkflowRoute(status: JobStatus): string {
  if (status === "hitl_pending") {
    return "review";
  }
  if (status === "completed") {
    return "result";
  }
  return "loading";
}

function reviewStorageKey(jobId: string): string {
  return `loss-run-review:${jobId}`;
}

export function loadReviewSnapshot(jobId: string): ReviewSnapshot | null {
  try {
    const raw = window.sessionStorage.getItem(reviewStorageKey(jobId));
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as ReviewSnapshot;
  } catch {
    return null;
  }
}

export function saveReviewSnapshot(jobId: string, snapshot: ReviewSnapshot): void {
  window.sessionStorage.setItem(reviewStorageKey(jobId), JSON.stringify(snapshot));
}

export function clearReviewSnapshot(jobId: string): void {
  window.sessionStorage.removeItem(reviewStorageKey(jobId));
}

export function buildJobFileUrl(jobId: string, fileId: string): string {
  const base = apiClient.defaults.baseURL ?? "http://localhost:8000";
  return `${base}/api/v1/jobs/${jobId}/files/${fileId}`;
}
