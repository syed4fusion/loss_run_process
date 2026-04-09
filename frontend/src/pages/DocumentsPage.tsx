import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getJob } from "../api/jobs";
import type { JobResponse } from "../types";
import { buildJobFileUrl } from "../workflow";

export default function DocumentsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = id ?? "";

  const [job, setJob] = useState<JobResponse | null>(null);
  const [selectedFileId, setSelectedFileId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setError("Missing job ID.");
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const nextJob = await getJob(jobId);
        if (cancelled) {
          return;
        }
        setJob(nextJob);
        setSelectedFileId((current) => current || nextJob.files[0]?.id || "");
      } catch (err: any) {
        if (cancelled) {
          return;
        }
        setError(err?.response?.data?.detail ?? "Unable to load documents.");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const selectedFile = job?.files.find((file) => file.id === selectedFileId) ?? job?.files[0];

  return (
    <main className="screen workflowScreen">
      <section className="workflowShell">
        <header className="pageHeader">
          <div>
            <p className="kicker">Source Documents</p>
            <h1>{job?.insured_name || "Document Viewer"}</h1>
            <p className="lede">Inspect the uploaded PDFs while you review extracted data.</p>
          </div>
          <div className="headerActions">
            <button type="button" className="secondaryButton" onClick={() => navigate(-1)}>
              Back
            </button>
            <Link className="secondaryButton" to={`/jobs/${jobId}/review`}>
              Review Page
            </Link>
          </div>
        </header>

        {error ? <p className="errorText">{error}</p> : null}

        <section className="documentWorkspace">
          <aside className="glassPanel documentSidebar">
            <p className="kicker">Uploaded PDFs</p>
            <div className="stackList">
              {job?.files.map((file) => (
                <button
                  key={file.id}
                  type="button"
                  className={`documentSelector ${selectedFile?.id === file.id ? "active" : ""}`}
                  onClick={() => setSelectedFileId(file.id)}
                >
                  <strong>{file.filename}</strong>
                  <span>{file.carrier_code || "Carrier pending"}</span>
                </button>
              ))}
            </div>
          </aside>

          <section className="glassPanel documentCanvasPanel">
            {selectedFile ? (
              <>
                <div className="sectionHead">
                  <div>
                    <p className="kicker">Viewing</p>
                    <h2>{selectedFile.filename}</h2>
                  </div>
                  <a
                    className="ghostLink"
                    href={buildJobFileUrl(jobId, selectedFile.id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open in new tab
                  </a>
                </div>
                <iframe
                  title={selectedFile.filename}
                  className="documentFrame"
                  src={buildJobFileUrl(jobId, selectedFile.id)}
                />
              </>
            ) : (
              <p className="mutedText">No uploaded documents are available.</p>
            )}
          </section>
        </section>
      </section>
    </main>
  );
}
