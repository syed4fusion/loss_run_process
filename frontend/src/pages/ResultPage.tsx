import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getJob } from "../api/jobs";
import { buildPdfUrl, getAnalytics, getClaims, getRedflags, getSummary } from "../api/outputs";
import type { AnalyticsResult, ClaimsArray, JobResponse, RedFlagReport, SummarySections } from "../types";
import {
  flattenClaims,
  formatCurrency,
  formatDate,
  formatFlagType,
  formatPercent,
  formatYearSpan,
  loadReviewSnapshot,
} from "../workflow";

const POLL_MS = 2000;

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = id ?? "";

  const [job, setJob] = useState<JobResponse | null>(null);
  const [summary, setSummary] = useState<SummarySections | null>(null);
  const [claims, setClaims] = useState<ClaimsArray | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResult | null>(null);
  const [redflags, setRedflags] = useState<RedFlagReport | null>(null);
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

    async function load() {
      try {
        const nextJob = await getJob(jobId);
        if (cancelled) {
          return;
        }
        setJob(nextJob);

        if (nextJob.status === "hitl_pending") {
          navigate(`/jobs/${jobId}/review`, { replace: true });
          return;
        }
        if (nextJob.status === "failed") {
          setLoading(false);
          setError(nextJob.error_message ?? "The workflow failed.");
          return;
        }

        if (nextJob.status !== "completed") {
          timer = window.setTimeout(load, POLL_MS);
          return;
        }

        const [summaryData, claimsData, analyticsData, redflagsData] = await Promise.all([
          getSummary(jobId),
          getClaims(jobId),
          getAnalytics(jobId),
          getRedflags(jobId),
        ]);
        if (cancelled) {
          return;
        }

        const reviewSnapshot = loadReviewSnapshot(jobId);
        setSummary(reviewSnapshot?.summary ?? summaryData);
        setClaims(reviewSnapshot?.claims ?? claimsData);
        setAnalytics(analyticsData);
        setRedflags(redflagsData);
        setLoading(false);
        setError(null);
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setLoading(false);
        setError(err?.response?.data?.detail ?? "Unable to load the final result.");
      }
    }

    load();
    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [jobId, navigate]);

  const finalClaims = useMemo(() => flattenClaims(claims), [claims]);

  return (
    <main className="screen workflowScreen">
      <section className="workflowShell">
        <header className="pageHeader">
          <div>
            <p className="kicker">Step 05</p>
            <h1>{job?.insured_name || "Final Result"}</h1>
            <p className="lede">
              Review the clean final package and download the generated PDF when you are ready.
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
          <article className="progressCard">Review</article>
          <article className="progressCard active">Result</article>
        </section>

        {loading ? (
          <section className="glassPanel heroStatus">
            <div className="statusCopy">
              <p className="kicker">Finalizing</p>
              <h2>Building the final report</h2>
              <p className="lede">The approved review is being converted into the final output package and PDF.</p>
            </div>
            <div className="signalTower" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </section>
        ) : null}

        {error ? <p className="errorText">{error}</p> : null}

        {!loading && summary && claims && analytics ? (
          <>
            <section className="statusBoard">
              <article className="glassPanel statCard">
                <span>Claims</span>
                <strong>{finalClaims.length}</strong>
              </article>
              <article className="glassPanel statCard">
                <span>Years</span>
                <strong>{formatYearSpan(analytics.years_analyzed ?? [])}</strong>
              </article>
              <article className="glassPanel statCard">
                <span>Loss Ratio</span>
                <strong>{formatPercent(analytics.overall_loss_ratio)}</strong>
              </article>
              <article className="glassPanel statCard">
                <span>Open Reserves</span>
                <strong>{formatCurrency(analytics.total_open_reserves)}</strong>
              </article>
            </section>

            <section className="resultCanvas">
              <div className="resultMain">
                <article className="glassPanel reportHero">
                  <div className="sectionHead">
                    <div>
                      <p className="kicker">Underwriter Report</p>
                      <h2>Formatted final output</h2>
                    </div>
                    <a className="primaryButton anchorButton" href={buildPdfUrl(jobId)} target="_blank" rel="noreferrer">
                      Download PDF
                    </a>
                  </div>
                  <div className="summaryBlocks">
                    <SummaryCard title="Executive Summary" body={summary.executive_summary} />
                    <SummaryCard title="Year-by-Year Analysis" body={summary.year_by_year} />
                    <SummaryCard title="Large Loss Detail" body={summary.large_loss_detail} />
                    <SummaryCard title="Open Claim Status" body={summary.open_claim_status} />
                    <SummaryCard title="Red Flag Disclosure" body={summary.red_flag_disclosure} />
                    <SummaryCard title="Risk Management Observations" body={summary.risk_management_observations} />
                    <SummaryCard title="Disclaimer" body={summary.disclaimer || ""} subtle />
                  </div>
                </article>

                <article className="glassPanel sectionPanel">
                  <p className="kicker">Reviewed Claims</p>
                  <h2>Extracted detail set</h2>
                  <div className="claimsLedger">
                    {claims.policy_periods.map((period) => (
                      <section key={`${period.carrier_code}-${period.period}`} className="ledgerPeriod">
                        <div className="sectionHead">
                          <div>
                            <strong>
                              {period.carrier_code} / {period.lob}
                            </strong>
                            <p className="mutedText">{period.period}</p>
                          </div>
                          <span className="ledgerAmount">{formatCurrency(period.earned_premium)}</span>
                        </div>
                        <div className="ledgerRows">
                          {period.claims.map((claim) => (
                            <article key={claim.claim_id} className="ledgerRow">
                              <div>
                                <strong>{claim.claim_type}</strong>
                                <p className="mutedText">
                                  {claim.claim_id} • {formatDate(claim.occurrence_date)} • {claim.status}
                                </p>
                                <p>{claim.description}</p>
                              </div>
                              <strong>{formatCurrency(claim.amount_incurred)}</strong>
                            </article>
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                </article>
              </div>

              <aside className="resultSide">
                <article className="glassPanel sectionPanel">
                  <p className="kicker">Red Flags</p>
                  <h2>Flag summary</h2>
                  <div className="stackList">
                    {(redflags?.flags ?? []).map((flag, index) => (
                      <div key={`${flag.flag_id ?? index}-${index}`} className={`flagPanel severity-${flag.severity ?? "warning"}`}>
                        <strong>{formatFlagType(flag.flag_type)}</strong>
                        <p>{flag.narrative || flag.rule_description || "No narrative available."}</p>
                      </div>
                    ))}
                    {(redflags?.flags ?? []).length === 0 ? <p className="mutedText">No red flags generated.</p> : null}
                  </div>
                </article>

                <article className="glassPanel sectionPanel">
                  <p className="kicker">Analytics Snapshot</p>
                  <h2>Portfolio metrics</h2>
                  <div className="metricStack">
                    <div>
                      <span>Severity Trend</span>
                      <strong>{formatPercent(analytics.severity_trend)}</strong>
                    </div>
                    <div>
                      <span>Frequency Trend</span>
                      <strong>{formatPercent(analytics.frequency_trend)}</strong>
                    </div>
                    <div>
                      <span>Large Loss Ratio</span>
                      <strong>{formatPercent(analytics.large_loss_ratio)}</strong>
                    </div>
                  </div>
                </article>

                <article className="glassPanel sectionPanel">
                  <p className="kicker">Extraction Notes</p>
                  <h2>Warnings and exceptions</h2>
                  <div className="stackList">
                    {(claims.extraction_notes ?? []).map((note, index) => (
                      <div key={`${note}-${index}`} className="notePanel">
                        {note}
                      </div>
                    ))}
                    {(claims.extraction_notes ?? []).length === 0 ? <p className="mutedText">No extraction notes.</p> : null}
                  </div>
                </article>
              </aside>
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}

function SummaryCard({ title, body, subtle = false }: { title: string; body: string; subtle?: boolean }) {
  return (
    <article className={`summaryCard ${subtle ? "subtleCard" : ""}`}>
      <h3>{title}</h3>
      <p>{body || "No content available."}</p>
    </article>
  );
}
