import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { approveHitl, editHitl, getHitlDetail } from "../api/hitl";
import { getJob } from "../api/jobs";
import type { ClaimRecord, ClaimsArray, HitlDetailResponse, JobResponse, SummarySections } from "../types";
import {
  EMPTY_SUMMARY,
  buildJobFileUrl,
  flattenClaims,
  formatCurrency,
  formatDate,
  formatFlagType,
  formatPercent,
  formatYearSpan,
  saveReviewSnapshot,
} from "../workflow";

const POLL_MS = 2500;

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = id ?? "";

  const [job, setJob] = useState<JobResponse | null>(null);
  const [review, setReview] = useState<HitlDetailResponse | null>(null);
  const [summary, setSummary] = useState<SummarySections>(EMPTY_SUMMARY);
  const [claims, setClaims] = useState<ClaimsArray | null>(null);
  const [reviewerId, setReviewerId] = useState("underwriter");
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setLoading(false);
      setError("Missing job ID.");
      return;
    }

    let cancelled = false;
    let timer: number | null = null;

    async function poll() {
      try {
        const nextJob = await getJob(jobId);
        if (cancelled) {
          return;
        }
        setJob(nextJob);

        if (nextJob.status === "completed") {
          navigate(`/jobs/${jobId}/result`, { replace: true });
          return;
        }
        if (nextJob.status !== "hitl_pending") {
          navigate(`/jobs/${jobId}/loading`, { replace: true });
          return;
        }
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setLoading(false);
        setError(err?.response?.data?.detail ?? "Unable to load the review package.");
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
  }, [jobId, navigate]);

  useEffect(() => {
    if (!jobId || job?.status !== "hitl_pending" || review) {
      return;
    }

    let cancelled = false;

    async function loadDetail() {
      try {
        const detail = await getHitlDetail(jobId);
        if (cancelled) {
          return;
        }
        setReview(detail);
        setSummary({ ...EMPTY_SUMMARY, ...detail.draft_summary });
        setClaims(JSON.parse(JSON.stringify(detail.claims)) as ClaimsArray);
        setLoading(false);
        setError(null);
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setLoading(false);
        setError(err?.response?.data?.detail ?? "Unable to load the review package.");
      }
    }

    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [job?.status, jobId, review]);

  const visibleClaims = useMemo(() => flattenClaims(claims), [claims]);
  const hasSummaryChanges = JSON.stringify(summary) !== JSON.stringify({ ...EMPTY_SUMMARY, ...review?.draft_summary });

  function updateClaim(claimId: string, field: keyof ClaimRecord, value: string) {
    setClaims((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        policy_periods: current.policy_periods.map((period) => ({
          ...period,
          claims: period.claims.map((claim) =>
            claim.claim_id === claimId ? { ...claim, [field]: value } : claim,
          ),
        })),
      };
    });
  }

  async function onContinue() {
    if (!jobId || !reviewerId.trim()) {
      setError("Reviewer ID is required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (claims) {
        saveReviewSnapshot(jobId, {
          claims,
          summary,
          updated_at: new Date().toISOString(),
        });
      }

      if (hasSummaryChanges) {
        await editHitl(jobId, reviewerId.trim(), summary);
      } else {
        await approveHitl(jobId, reviewerId.trim());
      }
      navigate(`/jobs/${jobId}/result`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Unable to submit the review.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="screen workflowScreen">
      <section className="workflowShell">
        <header className="pageHeader">
          <div>
            <p className="kicker">Step 04</p>
            <h1>{job?.insured_name || "Review Extracted Details"}</h1>
            <p className="lede">
              Review the extracted data, adjust the summary text if needed, inspect documents, and continue to the
              final package.
            </p>
          </div>
          <div className="headerActions">
            <Link className="secondaryButton" to={`/jobs/${jobId}/documents`}>
              View Documents
            </Link>
            <Link className="secondaryButton" to="/">
              New Upload
            </Link>
          </div>
        </header>

        <section className="progressNav">
          <article className="progressCard">Upload</article>
          <article className="progressCard">Prepare</article>
          <article className="progressCard active">Review</article>
          <article className="progressCard">Result</article>
        </section>

        {loading ? <p className="mutedText">Loading review package...</p> : null}
        {error ? <p className="errorText">{error}</p> : null}

        {review && claims ? (
          <>
            <section className="reviewStats">
              <article className="glassPanel statCard">
                <span>Policy Periods</span>
                <strong>{claims.policy_periods.length}</strong>
              </article>
              <article className="glassPanel statCard">
                <span>Claims</span>
                <strong>{visibleClaims.length}</strong>
              </article>
              <article className="glassPanel statCard">
                <span>Years</span>
                <strong>{formatYearSpan(review.analytics.years_analyzed ?? [])}</strong>
              </article>
              <article className="glassPanel statCard">
                <span>Overall Loss Ratio</span>
                <strong>{formatPercent(review.analytics.overall_loss_ratio ?? null)}</strong>
              </article>
            </section>

            <section className="reviewCanvas">
              <div className="reviewMain">
                <article className="glassPanel sectionPanel">
                  <div className="sectionHead">
                    <div>
                      <p className="kicker">Summary</p>
                      <h2>Adjust the drafted narrative</h2>
                    </div>
                    <label className="field compactField">
                      <span>Reviewer ID</span>
                      <input
                        type="text"
                        value={reviewerId}
                        onChange={(event) => setReviewerId(event.target.value)}
                        placeholder="underwriter"
                      />
                    </label>
                  </div>

                  <div className="editorColumns">
                    {renderSummaryField("Executive Summary", "executive_summary", summary, setSummary)}
                    {renderSummaryField("Year-by-Year Analysis", "year_by_year", summary, setSummary)}
                    {renderSummaryField("Large Loss Detail", "large_loss_detail", summary, setSummary)}
                    {renderSummaryField("Open Claim Status", "open_claim_status", summary, setSummary)}
                    {renderSummaryField("Red Flag Disclosure", "red_flag_disclosure", summary, setSummary)}
                    {renderSummaryField("Risk Management Observations", "risk_management_observations", summary, setSummary)}
                  </div>
                </article>

                <article className="glassPanel sectionPanel">
                  <div className="sectionHead">
                    <div>
                      <p className="kicker">Extracted Claims</p>
                      <h2>Check the extracted details</h2>
                    </div>
                    {job?.files[0] ? (
                      <a
                        className="ghostLink"
                        href={buildJobFileUrl(jobId, job.files[0].id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open First PDF
                      </a>
                    ) : null}
                  </div>

                  <div className="claimsReviewTable">
                    {visibleClaims.map((claim) => (
                      <article key={claim.claim_id} className="claimEditorCard">
                        <div className="claimEditorHeader">
                          <div>
                            <strong>{claim.claim_id}</strong>
                            <p className="mutedText">
                              {claim.carrier_code} / {claim.lob} / {claim.policy_period}
                            </p>
                          </div>
                          <span className={`statusPill status-${claim.status === "open" ? "running" : "complete"}`}>
                            {claim.status}
                          </span>
                        </div>
                        <div className="claimEditorGrid">
                          <label className="field">
                            <span>Claim Type</span>
                            <input
                              type="text"
                              value={claim.claim_type}
                              onChange={(event) => updateClaim(claim.claim_id, "claim_type", event.target.value)}
                            />
                          </label>
                          <label className="field">
                            <span>Status</span>
                            <input
                              type="text"
                              value={claim.status}
                              onChange={(event) => updateClaim(claim.claim_id, "status", event.target.value)}
                            />
                          </label>
                          <label className="field fieldWide">
                            <span>Description</span>
                            <textarea
                              value={claim.description}
                              rows={3}
                              onChange={(event) => updateClaim(claim.claim_id, "description", event.target.value)}
                            />
                          </label>
                          <label className="field">
                            <span>Occurrence Date</span>
                            <input
                              type="text"
                              value={claim.occurrence_date ?? ""}
                              onChange={(event) => updateClaim(claim.claim_id, "occurrence_date", event.target.value)}
                            />
                          </label>
                          <label className="field">
                            <span>Incurred</span>
                            <input
                              type="text"
                              value={claim.amount_incurred}
                              onChange={(event) => updateClaim(claim.claim_id, "amount_incurred", event.target.value)}
                            />
                          </label>
                          <label className="field">
                            <span>Reserved</span>
                            <input
                              type="text"
                              value={claim.amount_reserved}
                              onChange={(event) => updateClaim(claim.claim_id, "amount_reserved", event.target.value)}
                            />
                          </label>
                        </div>
                      </article>
                    ))}
                    {visibleClaims.length === 0 ? <p className="mutedText">No claims were extracted for review.</p> : null}
                  </div>
                </article>
              </div>

              <aside className="reviewSide">
                <article className="glassPanel sectionPanel">
                  <p className="kicker">Red Flags</p>
                  <h2>Confirmed signals</h2>
                  <div className="stackList">
                    {(review.red_flags.flags ?? []).map((flag, index) => (
                      <div key={`${flag.flag_id ?? index}-${index}`} className={`flagPanel severity-${flag.severity ?? "warning"}`}>
                        <strong>{formatFlagType(flag.flag_type)}</strong>
                        <p>{flag.narrative || flag.rule_description || "No narrative available."}</p>
                      </div>
                    ))}
                    {(review.red_flags.flags ?? []).length === 0 ? <p className="mutedText">No flags generated.</p> : null}
                  </div>
                </article>

                <article className="glassPanel sectionPanel">
                  <p className="kicker">Analytics</p>
                  <h2>Extracted account profile</h2>
                  <div className="metricStack">
                    <div>
                      <span>Open Reserves</span>
                      <strong>{formatCurrency(review.analytics.total_open_reserves)}</strong>
                    </div>
                    <div>
                      <span>Average Days To Close</span>
                      <strong>{review.analytics.avg_days_to_close?.toFixed(0) ?? "N/A"}</strong>
                    </div>
                    <div>
                      <span>Missing Years</span>
                      <strong>{review.analytics.missing_years?.join(", ") || "None"}</strong>
                    </div>
                  </div>
                </article>

                <article className="glassPanel sectionPanel">
                  <p className="kicker">Uploaded Documents</p>
                  <h2>Review source files</h2>
                  <div className="stackList">
                    {job?.files.map((file) => (
                      <a
                        key={file.id}
                        className="documentLink"
                        href={buildJobFileUrl(jobId, file.id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <span>{file.filename}</span>
                        <small>{file.carrier_code || "Pending carrier"}</small>
                      </a>
                    ))}
                  </div>
                </article>
              </aside>
            </section>

            <div className="actionRow">
              <Link className="secondaryButton" to={`/jobs/${jobId}/documents`}>
                Open Documents Workspace
              </Link>
              <button type="button" className="primaryButton" onClick={onContinue} disabled={submitting}>
                {submitting ? "Submitting Review..." : "Continue To Final Result"}
              </button>
            </div>
          </>
        ) : null}
      </section>
    </main>
  );
}

function renderSummaryField(
  label: string,
  key: keyof SummarySections,
  summary: SummarySections,
  setSummary: Dispatch<SetStateAction<SummarySections>>,
) {
  return (
    <label className="field" key={key}>
      <span>{label}</span>
      <textarea
        value={summary[key] ?? ""}
        rows={5}
        onChange={(event) => setSummary((current) => ({ ...current, [key]: event.target.value }))}
      />
    </label>
  );
}
