import { FormEvent, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createJob } from "../api/jobs";

const MAX_FILES = 10;

export default function NewJobPage() {
  const navigate = useNavigate();
  const [insuredName, setInsuredName] = useState("");
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
    if (!insuredName.trim()) {
      setError("Insured name is required.");
      return;
    }
    if (files.length === 0) {
      setError("Upload at least one PDF file.");
      return;
    }
    setIsSubmitting(true);
    try {
      const job = await createJob(insuredName.trim(), files);
      navigate(`/jobs/${job.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Unable to create job.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="page">
      <section className="card">
        <h1>New Loss Run Job</h1>
        <p className="subtle">Upload PDF files and start a backend triage pipeline.</p>
        <form onSubmit={onSubmit} className="stack">
          <label className="stack">
            <span>Insured Name</span>
            <input
              type="text"
              value={insuredName}
              onChange={(e) => setInsuredName(e.target.value)}
              placeholder="Example: Westech Mechanical Inc"
              required
            />
          </label>
          <label className="stack">
            <span>PDF Files (max {MAX_FILES})</span>
            <input type="file" accept=".pdf,application/pdf" multiple onChange={onFileChange} />
          </label>
          {files.length > 0 ? (
            <ul className="fileList">
              {files.map((file) => (
                <li key={file.name}>{file.name}</li>
              ))}
            </ul>
          ) : null}
          {error ? <p className="error">{error}</p> : null}
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating..." : "Create Job"}
          </button>
        </form>
      </section>
    </main>
  );
}
