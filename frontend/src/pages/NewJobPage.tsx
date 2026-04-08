import { FormEvent, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createJob } from "../api/jobs";

const MAX_FILES = 10;

export default function NewJobPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    const pdfs = selected.filter((file) => file.name.toLowerCase().endsWith(".pdf"));
    setFiles(pdfs.slice(0, MAX_FILES));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (files.length === 0) {
      setError("Upload at least one PDF file.");
      return;
    }
    setIsSubmitting(true);
    try {
      const job = await createJob(files);
      navigate(`/jobs/${job.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Unable to upload files.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="page shellPage">
      <section className="heroCard">
        <div className="heroHeader">
          <p className="eyebrow">Loss Run Processor</p>
          <h1>Create a job</h1>
          <p className="heroCopy">
            Upload PDF loss runs, create the job, then move through draft generation, review, and final delivery.
          </p>
        </div>

        <div className="flowRail">
          <div className="flowStep">
            <span className="flowIndex">01</span>
            <div>
              <h2>Extraction</h2>
              <p>Upload the source PDFs.</p>
            </div>
          </div>
          <div className="flowStep">
            <span className="flowIndex">02</span>
            <div>
              <h2>HITL Review</h2>
              <p>Review, edit, approve, or reject the draft.</p>
            </div>
          </div>
          <div className="flowStep">
            <span className="flowIndex">03</span>
            <div>
              <h2>Final Result</h2>
              <p>Open the final summary and PDF.</p>
            </div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="uploadPanel">
          <label className="uploadDropzone">
            <input type="file" accept=".pdf,application/pdf" multiple onChange={onFileChange} />
            <span className="uploadPrompt">Select up to {MAX_FILES} PDF files</span>
            <span className="uploadHint">PDF only. Job processing starts from the workflow page.</span>
          </label>

          {files.length > 0 ? (
            <ul className="selectedFileList">
              {files.map((file) => (
                <li key={`${file.name}-${file.size}`}>
                  <span>{file.name}</span>
                  <span>{formatFileSize(file.size)}</span>
                </li>
              ))}
            </ul>
          ) : null}

          {error ? <p className="error">{error}</p> : null}

          <div className="uploadActions">
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Creating Job..." : "Create Job"}
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
  const kb = bytes / 1024;
  return `${Math.max(kb, 1).toFixed(0)} KB`;
}
