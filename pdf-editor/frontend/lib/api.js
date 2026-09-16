const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function postFiles(path, formData) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      msg = data.detail || msg;
    } catch {}
    throw new Error(msg);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "download";
  return { blob, filename };
}

export function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function mergePdfs(files) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return postFiles("/merge", fd);
}

export async function splitPdf(file, ranges) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("ranges", ranges);
  return postFiles("/split", fd);
}

export async function compressPdf(file, quality = "medium") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("quality", quality);
  return postFiles("/compress", fd);
}

export async function rotatePdf(file, degrees, pages = "all") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("degrees", degrees);
  fd.append("pages", pages);
  return postFiles("/rotate", fd);
}

export async function deletePages(file, pages) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("pages", pages);
  return postFiles("/delete-pages", fd);
}

export async function pdfToImages(file, dpi = 150) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("dpi", dpi);
  return postFiles("/to-images", fd);
}

// --- Text editor flow -------------------------------------------------

export async function extractText(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/extract-text`, { method: "POST", body: fd });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Extraction failed (${res.status})`);
  }
  return res.json();
}

export function pageImageUrl(jobId, pageNum, dpi = 150) {
  return `${API_BASE}/page-image/${jobId}/${pageNum}?dpi=${dpi}`;
}

export async function applyEdits(jobId, edits) {
  const res = await fetch(`${API_BASE}/apply-edits/${jobId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ edits }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Save failed (${res.status})`);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  return { blob, filename: match ? match[1] : "edited.pdf" };
}
