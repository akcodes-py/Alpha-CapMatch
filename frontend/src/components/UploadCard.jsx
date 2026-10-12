import { useState } from "react";
import { api } from "../api.js";

export default function UploadCard({ org, onImported }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(null);
  const [isPreview, setIsPreview] = useState(false);
  const [error, setError] = useState("");

  async function run(fn, preview) {
    if (!file) return;
    setBusy(true);
    setError("");
    setSummary(null);
    try {
      const result = await fn();
      setSummary(result);
      setIsPreview(preview);
      if (!preview) onImported();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const handleUpload = () => run(() => api.importCsv(org, file), false);
  const handlePreview = () => run(() => api.previewCsv(org, file), true);

  return (
    <section className="card" id="upload">
      <h2>Upload bank statement</h2>
      <div className="row">
        <input
          type="file"
          accept=".csv"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
        <button className="btn" disabled={!file || busy} onClick={handleUpload}>
          {busy ? "Uploading…" : "Upload"}
        </button>
        <button className="btn" disabled={!file || busy} onClick={handlePreview}>
          {busy ? "…" : "Preview"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {summary && (
        <div className="summary">
          {isPreview && <p className="muted">Preview (nothing saved)</p>}
          <p>
            {isPreview ? "Would import" : "Imported"} {summary.imported ?? summary.would_import},{" "}
            duplicates {summary.duplicates}, errors {summary.errors.length}
          </p>
          {summary.by_status && (
            <p className="muted">
              Suggested {summary.by_status.suggested}, needs review{" "}
              {summary.by_status.needs_review}, ignored {summary.by_status.ignored}
            </p>
          )}
          {summary.errors.length > 0 && (
            <ul>
              {summary.errors.map((e) => (
                <li key={e.line}>
                  Line {e.line}: {e.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
