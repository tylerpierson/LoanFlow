const API_BASE = "http://localhost:8000";

export async function analyzePdf(file, jobId) {
  const formData = new FormData();

  formData.append("file", file);
  formData.append("job_id", jobId);

  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error("Failed to analyze PDF");
  }

  return res.json();
}

export async function getProgress(jobId) {
  const res = await fetch(`${API_BASE}/progress/${jobId}`);

  if (!res.ok) {
    throw new Error("Failed to get progress");
  }

  return res.json();
}

export async function splitPdf(jobId, sections, client) {
  const res = await fetch(`${API_BASE}/split/${jobId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      sections,
      client,
    }),
  });

  if (!res.ok) {
    throw new Error("Failed to split PDF");
  }

  return res.json();
}

export async function uploadZipToGoogleDrive(jobId) {
  const res = await fetch(
    `${API_BASE}/upload-to-google-drive/${jobId}`,
    {
      method: "POST",
    }
  );

  if (!res.ok) {
    throw new Error("Failed to upload ZIP to Google Drive");
  }

  return res.json();
}

export function fullDownloadUrl(path) {
  if (!path) return "";

  if (path.startsWith("http")) {
    return path;
  }

  return `${API_BASE}${path}`;
}