import { useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createJob, runJob } from "../api/jobs";
import { clearReviewSnapshot } from "../workflow";

const MAX_FILES = 10;

export default function UploadPage() {
  const navigate = useNavigate();
  const [insuredName, setInsuredName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []).filter((file) =>
      file.name.toLowerCase().endsWith(".pdf"),
    );
    setFiles(selected.slice(0, MAX_FILES));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (files.length === 0) {
      setError("Select at least one PDF file.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const job = await createJob(files, insuredName);
      clearReviewSnapshot(job.id);
      await runJob(job.id);
      navigate(`/jobs/${job.id}/loading`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Unable to create and start the job.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="screen shellScreen">
      <section className="uploadHero">
        <div className="heroLead">
          <p className="kicker">Loss Run Workflow</p>
          <h1>Upload PDFs and launch the review run.</h1>
          <p className="lede">
            The workflow starts here. Upload only PDF loss runs, generate the job ID, and move directly into
            processing.
          </p>
        </div>

        <div className="stepRibbon">
          <article>
            <span>01</span>
            <strong>Upload PDFs</strong>
            <p>Only PDF documents are accepted.</p>
          </article>
          <article>
            <span>02</span>
            <strong>Create Job</strong>
            <p>The job ID is created and started immediately.</p>
          </article>
          <article>
            <span>03</span>
            <strong>Review Output</strong>
            <p>Wait for extraction, then review and finalize.</p>
          </article>
        </div>

        <form className="glassPanel uploadForm" onSubmit={onSubmit}>
          <div className="fieldGrid">
            <label className="field">
              <span>Insured Name</span>
              <input
                type="text"
                value={insuredName}
                onChange={(event) => setInsuredName(event.target.value)}
                placeholder="Optional. Defaults to the first file name."
              />
            </label>
          </div>

          <label className="dropZone">
            <input type="file" accept=".pdf,application/pdf" multiple onChange={onFileChange} />
            <span className="dropTitle">Choose up to {MAX_FILES} PDF files</span>
            <span className="dropHint">Non-PDF files are ignored. The job starts as soon as you submit.</span>
          </label>

          <div className="selectedGrid">
            {files.map((file) => (
              <article key={`${file.name}-${file.size}`} className="fileChip">
                <div>
                  <strong>{file.name}</strong>
                  <p>{formatFileSize(file.size)}</p>
                </div>
                <span>PDF</span>
              </article>
            ))}
            {files.length === 0 ? <p className="mutedText">No PDFs selected yet.</p> : null}
          </div>

          {error ? <p className="errorText">{error}</p> : null}

          <div className="actionRow">
            <button type="submit" className="primaryButton" disabled={submitting}>
              {submitting ? "Creating Job..." : "Create Job and Start"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

function formatFileSize(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) {
    return `${mb.toFixed(1)} MB`;
  }
  const kb = Math.max(bytes / 1024, 1);
  return `${kb.toFixed(0)} KB`;
}
