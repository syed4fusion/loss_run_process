import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getJob } from "../api/jobs";
import { buildPdfUrl, getSummary } from "../api/outputs";
import type { JobResponse } from "../types";

const POLL_MS = 4000;

export default function JobStatusPage() {
  const { id } = useParams<{ id: string }>();
  const jobId = id ?? "";
  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);

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
        setError(null);
        setLoading(false);

        if (data.status !== "completed" && data.status !== "failed") {
          timer = window.setTimeout(poll, POLL_MS);
        }
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setLoading(false);
        setError(err?.response?.data?.detail ?? "Unable to fetch job.");
        timer = window.setTimeout(poll, POLL_MS);
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

  async function onViewSummary() {
    if (!jobId) {
      return;
    }
    try {
      const data = await getSummary(jobId);
      setSummary(JSON.stringify(data, null, 2));
    } catch (err: any) {
      setSummary(`Error fetching summary: ${err?.response?.data?.detail ?? "unknown error"}`);
    }
  }

  return (
    <main className="page">
      <section className="card">
        <div className="headerRow">
          <h1>Job Status</h1>
          <Link to="/">Create another job</Link>
        </div>

        {loading ? <p>Loading job...</p> : null}
        {error ? <p className="error">{error}</p> : null}

        {job ? (
          <div className="stack">
            <p><b>Insured:</b> {job.insured_name}</p>
            <p><b>Job ID:</b> {job.id}</p>
            <p><b>Status:</b> <span className={`badge badge-${job.status}`}>{job.status}</span></p>
            <p><b>Current Stage:</b> {job.current_stage ?? "n/a"}</p>
            {job.error_message ? <p className="error">Pipeline error: {job.error_message}</p> : null}
            <h3>Files</h3>
            <ul className="fileList">
              {job.files.map((file) => (
                <li key={file.id}>
                  {file.filename} ({file.extraction_status})
                </li>
              ))}
            </ul>

            {job.status === "completed" ? (
              <div className="row">
                <button onClick={onViewSummary}>View Summary JSON</button>
                <a href={buildPdfUrl(job.id)} target="_blank" rel="noreferrer">
                  Download PDF
                </a>
              </div>
            ) : null}
          </div>
        ) : null}

        {summary ? (
          <>
            <h3>Summary JSON</h3>
            <pre>{summary}</pre>
          </>
        ) : null}
      </section>
    </main>
  );
}
