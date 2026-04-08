import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { approveHitl, editHitl, getHitlDetail, rejectHitl } from "../api/hitl";
import { getJob, runJob } from "../api/jobs";
import { buildPdfUrl, getAnalytics, getClaims, getRedflags, getSummary } from "../api/outputs";
import type {
  AnalyticsResult,
  ClaimsArray,
  HitlDetailResponse,
  JobResponse,
  RedFlagReport,
  SummarySections,
} from "../types";

const POLL_MS = 2500;

const EMPTY_SUMMARY: SummarySections = {
  executive_summary: "",
  year_by_year: "",
  large_loss_detail: "",
  open_claim_status: "",
  red_flag_disclosure: "",
  risk_management_observations: "",
  disclaimer: "",
};

const STAGE_LABELS: Record<string, string> = {
  pending: "Preparing job",
  ingest: "Validating uploads",
  extract: "Extracting claims",
  normalize: "Normalizing claims",
  analytics: "Calculating analytics",
  redflags: "Building red flags",
  summary: "Drafting underwriter summary",
  hitl_pending: "Awaiting human review",
  deliver: "Generating final PDF",
  completed: "Completed",
  failed: "Failed",
};

export default function JobStatusPage() {
  const { id } = useParams<{ id: string }>();
  const jobId = id ?? "";

  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const [hitlLoading, setHitlLoading] = useState(false);
  const [hitl, setHitl] = useState<HitlDetailResponse | null>(null);
  const [editSections, setEditSections] = useState<SummarySections>(EMPTY_SUMMARY);
  const [hitlUserId, setHitlUserId] = useState("underwriter");
  const [rejectReason, setRejectReason] = useState("");
  const [hitlActionLoading, setHitlActionLoading] = useState(false);
  const [hitlActionError, setHitlActionError] = useState<string | null>(null);

  const [finalSummary, setFinalSummary] = useState<SummarySections | null>(null);
  const [finalClaims, setFinalClaims] = useState<ClaimsArray | null>(null);
  const [finalAnalytics, setFinalAnalytics] = useState<AnalyticsResult | null>(null);
  const [finalRedflags, setFinalRedflags] = useState<RedFlagReport | null>(null);
  const [finalLoading, setFinalLoading] = useState(false);

  useEffect(() => {
    if (!jobId) {
      setError("Missing job id in route.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    let timer: number | null = null;

    async function poll() {
      try {
        const data = await getJob(jobId);
        if (cancelled) {
          return;
        }
        setJob(data);
        setLoading(false);
        setError(null);
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setError(err?.response?.data?.detail ?? "Unable to fetch job status.");
        setLoading(false);
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(poll, POLL_MS);
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [jobId]);

  useEffect(() => {
    if (!jobId || job?.status !== "hitl_pending") {
      return;
    }
    let cancelled = false;

    async function fetchHitl() {
      setHitlLoading(true);
      setHitlActionError(null);
      try {
        const data = await getHitlDetail(jobId);
        if (cancelled) {
          return;
        }
        setHitl(data);
        setEditSections({
          ...EMPTY_SUMMARY,
          ...data.draft_summary,
        });
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setHitlActionError(err?.response?.data?.detail ?? "Failed to load review package.");
      } finally {
        if (!cancelled) {
          setHitlLoading(false);
        }
      }
    }

    fetchHitl();
    return () => {
      cancelled = true;
    };
  }, [job?.status, jobId]);

  useEffect(() => {
    if (!jobId || job?.status !== "completed") {
      return;
    }
    if (finalSummary && finalClaims && finalAnalytics && finalRedflags) {
      return;
    }

    let cancelled = false;

    async function fetchFinal() {
      setFinalLoading(true);
      try {
        const [summary, claims, analytics, redflags] = await Promise.all([
          getSummary(jobId),
          getClaims(jobId),
          getAnalytics(jobId),
          getRedflags(jobId),
        ]);
        if (cancelled) {
          return;
        }
        setFinalSummary(summary);
        setFinalClaims(claims);
        setFinalAnalytics(analytics);
        setFinalRedflags(redflags);
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setError(err?.response?.data?.detail ?? "Failed to fetch final report data.");
      } finally {
        if (!cancelled) {
          setFinalLoading(false);
        }
      }
    }

    fetchFinal();
    return () => {
      cancelled = true;
    };
  }, [finalAnalytics, finalClaims, finalRedflags, finalSummary, job?.status, jobId]);

  async function onStartPipeline() {
    if (!jobId) {
      return;
    }
    setStarting(true);
    setError(null);
    try {
      await runJob(jobId);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Unable to start draft generation.");
    } finally {
      setStarting(false);
    }
  }

  async function onApprove() {
    if (!jobId || !hitlUserId.trim()) {
      setHitlActionError("Reviewer ID is required.");
      return;
    }
    setHitlActionLoading(true);
    setHitlActionError(null);
    try {
      await approveHitl(jobId, hitlUserId.trim());
      setHitl(null);
    } catch (err: any) {
      setHitlActionError(err?.response?.data?.detail ?? "Unable to approve summary.");
    } finally {
      setHitlActionLoading(false);
    }
  }

  async function onSaveAndApprove() {
    if (!jobId || !hitlUserId.trim()) {
      setHitlActionError("Reviewer ID is required.");
      return;
    }
    setHitlActionLoading(true);
    setHitlActionError(null);
    try {
      await editHitl(jobId, hitlUserId.trim(), editSections);
      setHitl(null);
    } catch (err: any) {
      setHitlActionError(err?.response?.data?.detail ?? "Unable to submit edits.");
    } finally {
      setHitlActionLoading(false);
    }
  }

  async function onReject() {
    if (!jobId || !hitlUserId.trim()) {
      setHitlActionError("Reviewer ID is required.");
      return;
    }
    if (!rejectReason.trim()) {
      setHitlActionError("Add a rejection reason.");
      return;
    }
    setHitlActionLoading(true);
    setHitlActionError(null);
    try {
      await rejectHitl(jobId, hitlUserId.trim(), rejectReason.trim());
      setRejectReason("");
      setHitl(null);
    } catch (err: any) {
      setHitlActionError(err?.response?.data?.detail ?? "Unable to reject summary.");
    } finally {
      setHitlActionLoading(false);
    }
  }

  const displayName = job?.insured_name || extractDisplayName(job?.files?.[0]?.filename);
  const isReadyToStart = job?.status === "pending" && !job?.current_stage;
  const isProcessing = job?.status === "running" || (job?.status === "pending" && !!job?.current_stage);
  const currentStageLabel = isReadyToStart
    ? "Ready to start"
    : (STAGE_LABELS[job?.current_stage ?? "pending"] ?? (job?.current_stage || "Processing"));
  const allClaims = flattenClaims(hitl?.claims ?? finalClaims);
  const currentFlags = hitl?.red_flags?.flags ?? finalRedflags?.flags ?? [];
  const currentYears = hitl?.analytics?.years_analyzed ?? finalAnalytics?.years_analyzed ?? [];

  return (
    <main className="page workflowPage">
      <section className="workflowCard">
        <div className="workflowTopbar">
          <div>
            <p className="eyebrow">Workflow</p>
            <h1>{displayName}</h1>
            <p className="heroCopy">{getHeadlineMessage(job?.status, currentStageLabel)}</p>
          </div>
          <Link to="/" className="secondaryLink">New Job</Link>
        </div>

        {loading ? <p>Loading workflow...</p> : null}
        {error ? <p className="error">{error}</p> : null}

        {job ? (
          <>
            <WorkflowSteps status={job.status} />

            <section className="statusStrip">
              <div>
                <span className={`badge badge-${job.status}`}>{formatStatus(job.status)}</span>
                <p className="statusHeadline">{currentStageLabel}</p>
              </div>
              <div className="statusMeta">
                <span>{job.files.length} PDF{job.files.length === 1 ? "" : "s"}</span>
                <span>Job ID {job.id}</span>
              </div>
            </section>

            {isReadyToStart ? renderReadyToStart() : null}
            {isProcessing ? renderProcessing(job, currentStageLabel) : null}
            {job.status === "hitl_pending" ? renderHitl() : null}
            {job.status === "completed" ? renderFinal() : null}
            {job.status === "failed" ? renderFailed(job.error_message, onStartPipeline, starting) : null}

            <section className="supportGrid">
              <section className="sidebarPanel">
                <p className="eyebrow">Uploaded Files</p>
                <ul className="sidebarList">
                  {job.files.map((file) => (
                    <li key={file.id}>
                      <div>
                        <p className="sidebarTitle">{file.filename}</p>
                        <p className="subtle">{file.carrier_code || "Carrier pending"} / {file.lob_code || "LOB pending"}</p>
                      </div>
                      <span className={`badge badge-${mapExtractionToBadge(file.extraction_status)}`}>{file.extraction_status}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="sidebarPanel">
                <p className="eyebrow">Case Snapshot</p>
                <div className="metricGrid compactMetrics">
                  <MetricCard label="Claims" value={String(allClaims.length)} />
                  <MetricCard label="Flags" value={String(currentFlags.length)} />
                  <MetricCard label="Years" value={formatYearSpan(currentYears)} />
                  <MetricCard
                    label="Open Reserves"
                    value={formatCurrency(hitl?.analytics?.total_open_reserves ?? finalAnalytics?.total_open_reserves ?? null)}
                  />
                </div>
              </section>
            </section>
          </>
        ) : null}
      </section>
    </main>
  );

  function renderReadyToStart() {
    return (
      <section className="statePanel focusPanel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">Step 1</p>
            <h2>Start draft generation</h2>
          </div>
        </div>

        <ol className="instructionList">
          <li>Check that the uploaded files are correct.</li>
          <li>Start the draft generation.</li>
          <li>Review the draft when it appears.</li>
        </ol>

        <div className="actionBar">
          <button onClick={onStartPipeline} disabled={starting}>
            {starting ? "Starting Draft..." : "Start Draft Generation"}
          </button>
        </div>
      </section>
    );
  }

  function renderProcessing(currentJob: JobResponse, stageLabel: string) {
    return (
      <section className="statePanel statePanel-loading">
        <div className="loadingScene">
          <div className="pulseOrb" />
          <div>
            <p className="eyebrow">Step 1</p>
            <h2>{stageLabel}</h2>
            <p className="subtle">Stay on this screen. The draft review step will open automatically when processing finishes.</p>
          </div>
        </div>

        <div className="extractionBoard">
          {currentJob.files.map((file) => (
            <article key={file.id} className="fileStatusCard">
              <div className="rowBetween">
                <h3>{file.filename}</h3>
                <span className={`badge badge-${mapExtractionToBadge(file.extraction_status)}`}>{file.extraction_status}</span>
              </div>
              <p className="subtle">{describeFileStatus(currentJob.current_stage, file.extraction_status)}</p>
            </article>
          ))}
        </div>
      </section>
    );
  }

  function renderHitl() {
    return (
      <section className="statePanel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">Step 2</p>
            <h2>Review the draft and choose one outcome</h2>
          </div>
        </div>

        {hitlLoading ? <p>Loading review package...</p> : null}

        <div className="metricGrid compactMetrics">
          <MetricCard label="Policy Periods" value={String(hitl?.claims?.policy_periods?.length ?? 0)} />
          <MetricCard label="Claims" value={String(flattenClaims(hitl?.claims).length)} />
          <MetricCard label="Flags" value={String(hitl?.red_flags?.flags?.length ?? 0)} />
          <MetricCard label="Years" value={formatYearSpan(hitl?.analytics?.years_analyzed ?? [])} />
        </div>

        <div className="reviewLayout">
          <section className="summaryEditorCard">
            <h3>Draft Summary</h3>
            <p className="subtle sectionIntro">Edit any section that needs correction. If the draft is already acceptable, approve it as-is.</p>
            <div className="editorGrid">
              {renderSummaryEditor("Executive Summary", "executive_summary")}
              {renderSummaryEditor("Year-by-Year Analysis", "year_by_year")}
              {renderSummaryEditor("Large Loss Detail", "large_loss_detail")}
              {renderSummaryEditor("Open Claim Status", "open_claim_status")}
              {renderSummaryEditor("Red Flag Disclosure", "red_flag_disclosure")}
              {renderSummaryEditor("Risk Management Observations", "risk_management_observations")}
            </div>
          </section>

          <section className="reviewSidebar">
            <article className="infoCard">
              <h3>Reviewer</h3>
              <label className="stack">
                <span>Reviewer ID</span>
                <input
                  type="text"
                  value={hitlUserId}
                  onChange={(event) => setHitlUserId(event.target.value)}
                  placeholder="underwriter"
                />
              </label>
            </article>

            <article className="infoCard">
              <h3>Red Flags</h3>
              <ul className="flagList">
                {(hitl?.red_flags?.flags ?? []).map((flag, idx) => (
                  <li key={`${flag.flag_id ?? idx}-${idx}`} className={`flag flag-${flag.severity ?? "warning"}`}>
                    <p className="flagTitle">{formatFlagType(flag.flag_type)}</p>
                    <p className="subtle">{flag.narrative || flag.rule_description || "No narrative available."}</p>
                  </li>
                ))}
                {(hitl?.red_flags?.flags ?? []).length === 0 ? <li className="emptyState">No flags generated.</li> : null}
              </ul>
            </article>

            <article className="infoCard">
              <h3>Claims Snapshot</h3>
              <div className="claimTable">
                {flattenClaims(hitl?.claims).slice(0, 8).map((claim) => (
                  <div key={claim.claim_id} className="claimRow">
                    <div>
                      <p className="claimTitle">{claim.claim_type || "Claim"}</p>
                      <p className="subtle">{claim.occurrence_date || "No occurrence date"} / {claim.status}</p>
                    </div>
                    <strong>{formatCurrency(claim.amount_incurred)}</strong>
                  </div>
                ))}
                {flattenClaims(hitl?.claims).length === 0 ? <p className="emptyState">No claims available.</p> : null}
              </div>
            </article>

            <article className="infoCard">
              <h3>Reject and Regenerate</h3>
              <p className="subtle sectionIntro">Use rejection only when the system needs to regenerate the draft.</p>
              <textarea
                value={rejectReason}
                onChange={(event) => setRejectReason(event.target.value)}
                rows={4}
                placeholder="Explain what needs to change in the regenerated summary."
              />
            </article>
          </section>
        </div>

        {hitlActionError ? <p className="error">{hitlActionError}</p> : null}

        <div className="actionBar">
          <button onClick={onApprove} disabled={hitlActionLoading}>Approve As-Is</button>
          <button onClick={onSaveAndApprove} disabled={hitlActionLoading}>Approve With Edits</button>
          <button className="dangerBtn" onClick={onReject} disabled={hitlActionLoading}>Reject and Regenerate</button>
        </div>
      </section>
    );
  }

  function renderFinal() {
    return (
      <section className="statePanel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">Step 3</p>
            <h2>Final underwriting package ready</h2>
          </div>
          <a className="primaryLink" href={buildPdfUrl(jobId)} target="_blank" rel="noreferrer">
            Download PDF
          </a>
        </div>

        {finalLoading ? <p>Loading final report...</p> : null}

        <div className="metricGrid compactMetrics">
          <MetricCard label="Claims" value={String(flattenClaims(finalClaims).length)} />
          <MetricCard label="Years" value={formatYearSpan(finalAnalytics?.years_analyzed ?? [])} />
          <MetricCard label="Loss Ratio" value={formatPercent(finalAnalytics?.overall_loss_ratio ?? null)} />
          <MetricCard label="Open Reserves" value={formatCurrency(finalAnalytics?.total_open_reserves ?? null)} />
        </div>

        <div className="finalLayout">
          <section className="finalSummaryCard">
            <SummaryBlock title="Executive Summary" content={finalSummary?.executive_summary} />
            <SummaryBlock title="Year-by-Year Analysis" content={finalSummary?.year_by_year} />
            <SummaryBlock title="Large Loss Detail" content={finalSummary?.large_loss_detail} />
            <SummaryBlock title="Open Claim Status" content={finalSummary?.open_claim_status} />
            <SummaryBlock title="Red Flag Disclosure" content={finalSummary?.red_flag_disclosure} />
            <SummaryBlock title="Risk Management Observations" content={finalSummary?.risk_management_observations} />
            <SummaryBlock title="Disclaimer" content={finalSummary?.disclaimer} subtle />
          </section>

          <section className="reviewSidebar">
            <article className="infoCard">
              <h3>Final Red Flags</h3>
              <ul className="flagList">
                {(finalRedflags?.flags ?? []).map((flag, idx) => (
                  <li key={`${flag.flag_id ?? idx}-${idx}`} className={`flag flag-${flag.severity ?? "warning"}`}>
                    <p className="flagTitle">{formatFlagType(flag.flag_type)}</p>
                    <p className="subtle">{flag.narrative || flag.rule_description || "No narrative available."}</p>
                  </li>
                ))}
                {(finalRedflags?.flags ?? []).length === 0 ? <li className="emptyState">No flags generated.</li> : null}
              </ul>
            </article>

            <article className="infoCard">
              <h3>Extraction Notes</h3>
              <ul className="noteList">
                {(finalClaims?.extraction_notes ?? []).slice(0, 10).map((note, idx) => (
                  <li key={`${note}-${idx}`}>{note}</li>
                ))}
                {(finalClaims?.extraction_notes ?? []).length === 0 ? <li className="emptyState">No extraction warnings.</li> : null}
              </ul>
            </article>
          </section>
        </div>
      </section>
    );
  }

  function renderSummaryEditor(label: string, key: keyof SummarySections) {
    return (
      <label className="stack" key={key}>
        <span>{label}</span>
        <textarea
          value={editSections[key] ?? ""}
          onChange={(event) => setEditSections((prev) => ({ ...prev, [key]: event.target.value }))}
          rows={6}
        />
      </label>
    );
  }
}

function WorkflowSteps({ status }: { status: JobResponse["status"] }) {
  const states = [
    { key: "extract", label: "Generate Draft" },
    { key: "hitl", label: "Review Draft" },
    { key: "final", label: "Final Package" },
  ];
  const activeIndex = status === "completed" ? 2 : status === "hitl_pending" ? 1 : 0;

  return (
    <section className="workflowSteps">
      {states.map((state, index) => (
        <div
          key={state.key}
          className={`workflowStepCard ${index < activeIndex ? "done" : ""} ${index === activeIndex ? "active" : ""}`}
        >
          <span>{String(index + 1).padStart(2, "0")}</span>
          <strong>{state.label}</strong>
        </div>
      ))}
    </section>
  );
}

function SummaryBlock({ title, content, subtle = false }: { title: string; content?: string; subtle?: boolean }) {
  return (
    <article className="summaryBlock">
      <h3>{title}</h3>
      <p className={subtle ? "subtle" : undefined}>{content || "No content available."}</p>
    </article>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="metricCard">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function renderFailed(
  errorMessage: string | null,
  onRetry: () => Promise<void>,
  starting: boolean,
) {
  return (
    <section className="statePanel statePanel-failed">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Workflow Failed</p>
          <h2>Draft generation stopped before review</h2>
        </div>
      </div>
      <p className="error">{errorMessage ?? "Unknown failure."}</p>
      <div className="actionBar">
        <button onClick={onRetry} disabled={starting}>
          {starting ? "Restarting..." : "Retry Draft Generation"}
        </button>
      </div>
    </section>
  );
}

function getHeadlineMessage(status: JobResponse["status"] | undefined, currentStageLabel: string): string {
  if (status === "completed") {
    return "The final underwriting package is ready. Review it online or download the PDF.";
  }
  if (status === "hitl_pending") {
    return "The draft is ready. Review it, make edits if needed, then approve or reject it.";
  }
  if (status === "failed") {
    return "Processing stopped before the review step. Check the files and retry draft generation.";
  }
  if (status === "running") {
    return `The system is working now: ${currentStageLabel}.`;
  }
  return "Your files are uploaded. Start draft generation when you are ready.";
}

function formatStatus(status: JobResponse["status"]): string {
  if (status === "hitl_pending") {
    return "Review Ready";
  }
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatCurrency(value: string | number | null): string {
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

function formatYearSpan(years: number[]): string {
  if (years.length === 0) {
    return "N/A";
  }
  if (years.length === 1) {
    return String(years[0]);
  }
  return `${Math.min(...years)}-${Math.max(...years)}`;
}

function flattenClaims(claimsArray?: ClaimsArray | null) {
  return (claimsArray?.policy_periods ?? []).flatMap((period) => period.claims ?? []);
}

function formatFlagType(flagType?: string): string {
  if (!flagType) {
    return "Flag";
  }
  return flagType.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function extractDisplayName(filename?: string): string {
  if (!filename) {
    return "Loss Run Submission";
  }
  return filename.replace(/\.pdf$/i, "");
}

function describeFileStatus(currentStage: string | null, extractionStatus: string): string {
  if (extractionStatus === "completed") {
    return "Extraction complete. Waiting for the next step.";
  }
  if (extractionStatus === "failed") {
    return "Extraction failed for this file.";
  }
  if (currentStage === "extract") {
    return "The document is currently being parsed.";
  }
  return "Queued for processing.";
}

function mapExtractionToBadge(status: string): "completed" | "running" | "failed" | "pending" {
  if (status === "completed") {
    return "completed";
  }
  if (status === "failed") {
    return "failed";
  }
  if (status === "processing") {
    return "running";
  }
  return "pending";
}
