import React, { useState } from "react";
import loanflowLogo from "./assets/loanflow_logo.png";
import {
  analyzePdf,
  splitPdf,
  fullDownloadUrl,
  getProgress,
  uploadZipToGoogleDrive,
} from "./api";

const CATEGORY_OPTIONS = [
  "Processing Notes",
  "Property Tax / Appraisal District",
  "DU Findings",
  "ID",
  "Credit Explanation Letter",
  "Credit Report",
  "Income Worksheet",
  "Paystub",
  "W-2",
  "Bank Statement",
  "Cashier's Check / Earnest Money",
  "Purchase Contract",
  "Loan Application",
  "Insurance",
  "Title",
  "Appraisal",
  "Disclosure",
  "Unknown",
];

export default function App() {
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [sections, setSections] = useState([]);
  const [outputs, setOutputs] = useState([]);
  const [zipUrl, setZipUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [reviewSection, setReviewSection] = useState(null);
  const [splitting, setSplitting] = useState(false);
  const [uploadingDrive, setUploadingDrive] = useState(false);

  const [clientFirstName, setClientFirstName] = useState("");
  const [clientLastName, setClientLastName] = useState("");

  const [collapsedSections, setCollapsedSections] = useState({
    upload: false,
    review: false,
    results: false,
  });

  const [progress, setProgress] = useState({
    current: 0,
    total: 0,
    status: "",
  });

  function expandSection(sectionName) {
    setCollapsedSections((prev) => ({
      ...prev,
      [sectionName]: false,
    }));
  }

  function isClientReady() {
    return clientFirstName.trim() && clientLastName.trim();
  }

  async function handleAnalyze() {
    if (!file || !isClientReady()) return;

    const newJobId = crypto.randomUUID();

    setLoading(true);
    setOutputs([]);
    setZipUrl("");
    setReviewSection(null);
    setJobId(newJobId);

    setCollapsedSections({
      upload: false,
      review: false,
      results: true,
    });

    setProgress({
      current: 0,
      total: 0,
      status: "Starting analysis...",
    });

    const interval = setInterval(async () => {
      try {
        const progressResult = await getProgress(newJobId);
        setProgress(progressResult);
      } catch {
        // ignore polling errors
      }
    }, 500);

    try {
      const result = await analyzePdf(file, newJobId);

      console.log("Analyzed sections:", result.sections);

      setJobId(result.jobId);
      setSections(result.sections);

      setCollapsedSections({
        upload: true,
        review: false,
        results: true,
      });
    } catch (error) {
      console.error(error);
      alert("Failed to analyze PDF.");
    }

    clearInterval(interval);

    setLoading(false);

    setProgress({
      current: 0,
      total: 0,
      status: "",
    });
  }

  function updateSection(index, field, value) {
    const updated = [...sections];

    if (field === "startPage" || field === "endPage") {
      value = Number(value);
      updated[index][field] = value;

      const newPages = [];

      for (let i = updated[index].startPage; i <= updated[index].endPage; i++) {
        newPages.push(i);
      }

      updated[index].pages = newPages;
    } else {
      updated[index][field] = value;
    }

    setSections(updated);

    if (reviewSection === sections[index]) {
      setReviewSection(updated[index]);
    }
  }

  function addSection() {
    setSections([
      ...sections,
      {
        category: "Unknown",
        startPage: 1,
        endPage: 1,
        pages: [1],
        confidence: 0,
      },
    ]);
  }

  function removeSection(index) {
    const sectionBeingRemoved = sections[index];
    const updated = sections.filter((_, i) => i !== index);

    setSections(updated);

    if (reviewSection === sectionBeingRemoved) {
      setReviewSection(null);
    }
  }

  async function handleSplit(closePreview = false) {
    if (splitting || !isClientReady()) return;

    setSplitting(true);

    try {
      const result = await splitPdf(jobId, sections, {
        firstName: clientFirstName.trim(),
        lastName: clientLastName.trim(),
      });

      if (result.error) {
        alert(result.error);
        setSplitting(false);
        return;
      }

      setOutputs(result.files || []);
      setZipUrl(result.zipUrl);

      if (closePreview) {
        setReviewSection(null);
      }

      setCollapsedSections({
        upload: true,
        review: true,
        results: false,
      });
    } catch (error) {
      console.error(error);
      alert("Failed to split PDF.");
    }

    setSplitting(false);
  }

  async function handleUploadToDrive() {
    if (!jobId) return;

    setUploadingDrive(true);

    try {
      const result = await uploadZipToGoogleDrive(jobId);

      console.log(result);

      if (result.error) {
        alert(result.error);
      } else {
        alert("ZIP uploaded to Google Drive successfully!");
      }
    } catch (error) {
      console.error(error);
      alert("Failed to upload ZIP to Google Drive.");
    }

    setUploadingDrive(false);
  }

  function getPreviewPages(section) {
    const start = Number(section.startPage);
    const end = Number(section.endPage);

    if (
      !Number.isFinite(start) ||
      !Number.isFinite(end) ||
      start < 1 ||
      end < start
    ) {
      return [];
    }

    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  }

  return (
    <div className="app">
      <header className="app-header">
        <img
        src={loanflowLogo}
        alt="LoanFlow"
        className="app-logo"
        />

        <p>
          Upload a mortgage PDF, review the detected sections, preview selected
          pages, and create clean organized document packages.
        </p>
      </header>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>1. Create Client & Upload Document</h2>

            {collapsedSections.upload && (
              <p className="section-summary">
                {clientLastName}, {clientFirstName}
                {file ? ` — ${file.name}` : ""}
              </p>
            )}
          </div>

          {collapsedSections.upload && (
            <button
              type="button"
              className="collapse-btn"
              onClick={() => expandSection("upload")}
            >
              Expand
            </button>
          )}
        </div>

        {!collapsedSections.upload && (
          <>
            <div className="client-fields">
              <input
                type="text"
                placeholder="Client First Name"
                value={clientFirstName}
                onChange={(e) => setClientFirstName(e.target.value)}
              />

              <input
                type="text"
                placeholder="Client Last Name"
                value={clientLastName}
                onChange={(e) => setClientLastName(e.target.value)}
              />
            </div>

            <input
            type="file"
            accept="application/pdf"
            disabled={!isClientReady()}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            />

            <button
              className="primary"
              onClick={handleAnalyze}
              disabled={!file || !isClientReady() || loading}
            >
              {loading ? "Analyzing..." : "Analyze PDF"}
            </button>
          </>
        )}
      </section>

      {loading && (
        <div className="loading-overlay">
          <div className="loading-card">
            <div className="spinner"></div>

            <h2>Analyzing Document</h2>

            <p>
              {progress.total > 0
                ? `Analyzing Page ${progress.current} out of ${progress.total}`
                : "Preparing document..."}
            </p>
          </div>
        </div>
      )}

      {sections.length > 0 && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>2. Review Sections</h2>

              {collapsedSections.review && (
                <p className="section-summary">
                  {sections.length} sections ready to split
                </p>
              )}
            </div>

            <div className="section-header-actions">
              {!collapsedSections.review && (
                <button onClick={addSection}>+ Add Section</button>
              )}

              {collapsedSections.review && (
                <button
                  type="button"
                  className="collapse-btn"
                  onClick={() => expandSection("review")}
                >
                  Expand
                </button>
              )}
            </div>
          </div>

          {!collapsedSections.review && (
            <>
              <div className="table">
                <div className="row header-row">
                  <div>Category</div>
                  <div>Start</div>
                  <div>End</div>
                  <div></div>
                </div>

                {sections.map((section, index) => (
                  <div className="row" key={`${section.category}-${index}`}>
                    <select
                      value={section.category}
                      onChange={(e) =>
                        updateSection(index, "category", e.target.value)
                      }
                    >
                      {CATEGORY_OPTIONS.map((option) => (
                        <option key={option}>{option}</option>
                      ))}
                    </select>

                    <input
                      type="number"
                      value={section.startPage}
                      min="1"
                      onChange={(e) =>
                        updateSection(index, "startPage", e.target.value)
                      }
                    />

                    <input
                      type="number"
                      value={section.endPage}
                      min="1"
                      onChange={(e) =>
                        updateSection(index, "endPage", e.target.value)
                      }
                    />

                    <div className="row-actions">
                      <button
                        type="button"
                        onClick={() => setReviewSection(section)}
                      >
                        Preview
                      </button>

                      <button
                        className="danger"
                        onClick={() => removeSection(index)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {reviewSection && jobId && (
                <div
                  key={`${jobId}-${reviewSection.category}-${reviewSection.startPage}-${reviewSection.endPage}`}
                  className="preview-overlay"
                >
                  <div className="preview-modal">
                    <div className="preview-header">
                      <div>
                        <h3>{reviewSection.category}</h3>

                        <p>
                          Previewing pages {reviewSection.startPage}–
                          {reviewSection.endPage}
                        </p>
                      </div>

                      <button
                        className="danger"
                        onClick={() => setReviewSection(null)}
                      >
                        Close
                      </button>
                    </div>

                    <div className="page-preview-list">
                      {getPreviewPages(reviewSection).map((pageNumber) => {
                        const previewUrl = `${fullDownloadUrl(
                          `/preview-page/${jobId}/${pageNumber}`
                        )}?v=${jobId}-${pageNumber}-${reviewSection.startPage}-${reviewSection.endPage}`;

                        return (
                          <div
                            className="page-preview-card"
                            key={`${jobId}-${pageNumber}`}
                          >
                            <div className="page-preview-label">
                              Page {pageNumber}
                            </div>

                            <img
                            src={loanflowLogo}
                            alt="LoanFlow"
                            className="app-logo"
                            />
                          </div>
                        );
                      })}
                    </div>

                    <div className="preview-actions">
                      <button
                        className="primary"
                        onClick={() => handleSplit(true)}
                        disabled={splitting}
                      >
                        {splitting ? "Splitting..." : "Confirm Split"}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <button
                className="primary"
                onClick={handleSplit}
                disabled={splitting || !isClientReady()}
              >
                {splitting ? "Creating Split PDFs..." : "Create Split PDFs"}
              </button>
            </>
          )}
        </section>
      )}

      {outputs.length > 0 && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>3. Download Results</h2>

              {collapsedSections.results && (
                <p className="section-summary">
                  {outputs.length} files created
                </p>
              )}
            </div>

            {collapsedSections.results && (
              <button
                type="button"
                className="collapse-btn"
                onClick={() => expandSection("results")}
              >
                Expand
              </button>
            )}
          </div>

          {!collapsedSections.results && (
            <>
              <div className="downloads">
                {outputs.map((file) => {
                  const url = fullDownloadUrl(file.downloadUrl);

                  return (
                    <div className="download-row" key={file.filename}>
                      <div>
                        <strong>{file.category}</strong>

                        <div className="small-text">
                          {file.filename || `Pages ${file.startPage}–${file.endPage}`}
                        </div>
                      </div>

                      <div className="download-actions">
                        <a href={url} download>
                          Download
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>

              {zipUrl && (
                <>
                  <a className="zip" href={fullDownloadUrl(zipUrl)} download>
                    Download All as ZIP
                  </a>

                  <button
                    className="primary"
                    onClick={handleUploadToDrive}
                    disabled={uploadingDrive}
                  >
                    {uploadingDrive
                      ? "Uploading..."
                      : "Upload ZIP to Google Drive"}
                  </button>
                </>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}