import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getJob, runJob } from "../api/jobs";
import type { JobResponse } from "../types";
import { getCurrentStageLabel } from "../workflow";

const POLL_MS = 2000;

export default function LoadingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = id ?? "";

  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

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
        setLoading(false);
        setError(null);

        if (nextJob.status === "hitl_pending") {
          navigate(`/jobs/${jobId}/review`, { replace: true });
          return;
        }
        if (nextJob.status === "completed") {
          navigate(`/jobs/${jobId}/result`, { replace: true });
          return;
        }
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setLoading(false);
        setError(err?.response?.data?.detail ?? "Unable to load the job.");
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

  async function onRetry() {
    if (!jobId) {
      return;
    }
    setRetrying(true);
    setError(null);
    try {
      await runJob(jobId);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Unable to restart the job.");
    } finally {
      setRetrying(false);
    }
  }

  const stageLabel = getCurrentStageLabel(job);

  return (
    <main className="screen workflowScreen">
      <section className="workflowShell">
        <Header
          step="03"
          title={job?.insured_name || "Preparing Workflow"}
          subtitle="The extraction run is in progress. This screen waits until the review package is ready."
        />

        <ProgressNav current="loading" />

        <section className="glassPanel heroStatus">
          <div className="statusCopy">
            <p className="kicker">Processing</p>
            <h2>{loading ? "Loading job..." : stageLabel}</h2>
            <p className="lede">
              {job?.status === "failed"
                ? "The run stopped before review. Fix the issue and restart the job."
                : "Stay on this page while the system extracts documents and prepares the HITL review package."}
            </p>
          </div>
          <div className="signalTower" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
        </section>

        {error ? <p className="errorText">{error}</p> : null}

        {job ? (
          <section className="statusBoard">
            <article className="glassPanel statCard">
              <span>Job ID</span>
              <strong>{job.id}</strong>
            </article>
            <article className="glassPanel statCard">
              <span>Status</span>
              <strong>{job.status}</strong>
            </article>
            <article className="glassPanel statCard">
              <span>Current Stage</span>
              <strong>{stageLabel}</strong>
            </article>
            <article className="glassPanel statCard">
              <span>Documents</span>
              <strong>{job.files.length}</strong>
            </article>
          </section>
        ) : null}

        <section className="documentQueue">
          {job?.files.map((file) => (
            <article key={file.id} className="glassPanel queueCard">
              <div>
                <p className="queueTitle">{file.filename}</p>
                <p className="mutedText">
                  {file.carrier_code || "Carrier pending"} / {file.lob_code || "LOB pending"}
                </p>
              </div>
              <span className={`statusPill status-${mapFileStatus(file.extraction_status)}`}>{file.extraction_status}</span>
            </article>
          ))}
        </section>

        <div className="actionRow">
          <Link className="secondaryButton" to="/">
            New Upload
          </Link>
          {job?.status === "failed" ? (
            <button type="button" className="primaryButton" onClick={onRetry} disabled={retrying}>
              {retrying ? "Restarting..." : "Restart Job"}
            </button>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function Header({ step, title, subtitle }: { step: string; title: string; subtitle: string }) {
  return (
    <header className="pageHeader">
      <div>
        <p className="kicker">Step {step}</p>
        <h1>{title}</h1>
        <p className="lede">{subtitle}</p>
      </div>
      <Link className="secondaryButton" to="/">
        Exit Workflow
      </Link>
    </header>
  );
}

function ProgressNav({ current }: { current: "loading" | "review" | "result" }) {
  const steps = [
    { key: "upload", label: "Upload" },
    { key: "loading", label: "Prepare" },
    { key: "review", label: "Review" },
    { key: "result", label: "Result" },
  ];

  return (
    <section className="progressNav">
      {steps.map((step) => (
        <article key={step.key} className={`progressCard ${step.key === current ? "active" : ""}`}>
          <span>{step.label}</span>
        </article>
      ))}
    </section>
  );
}

function mapFileStatus(status: string): "pending" | "running" | "complete" | "failed" {
  if (status === "completed") {
    return "complete";
  }
  if (status === "processing") {
    return "running";
  }
  if (status === "failed") {
    return "failed";
  }
  return "pending";
}
