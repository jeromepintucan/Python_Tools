"use client";

import { useState, useRef, useCallback } from "react";
import { extractText, pageImageUrl, applyEdits, downloadBlob } from "../../lib/api";

const DPI = 150;
const PT_TO_PX = DPI / 72;

export default function Editor() {
  const [jobId, setJobId] = useState(null);
  const [pages, setPages] = useState([]); // [{page, width, height, lines: [...]}]
  const [currentPage, setCurrentPage] = useState(0);
  const [activeLineId, setActiveLineId] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | loading | ready | saving | error
  const [errorMsg, setErrorMsg] = useState("");
  const fileInputRef = useRef(null);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setStatus("loading");
    setErrorMsg("");
    try {
      const data = await extractText(file);
      setJobId(data.job_id);
      // Deep copy lines so we can track edited text separately from original
      setPages(
        data.pages.map((p) => ({
          ...p,
          lines: p.lines.map((l) => ({ ...l, originalText: l.text })),
        }))
      );
      setCurrentPage(0);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err.message || "Failed to read PDF");
    }
  };

  const updateLineText = useCallback((pageIdx, lineId, newText) => {
    setPages((prev) => {
      const next = [...prev];
      const page = { ...next[pageIdx] };
      page.lines = page.lines.map((l) => (l.id === lineId ? { ...l, text: newText } : l));
      next[pageIdx] = page;
      return next;
    });
  }, []);

  const handleSave = async () => {
    const edits = [];
    pages.forEach((page) => {
      page.lines.forEach((line) => {
        if (line.text !== line.originalText) {
          edits.push({
            page: page.page,
            bbox: line.bbox,
            font: line.font,
            size: line.size,
            color: line.color,
            text: line.text,
          });
        }
      });
    });

    if (edits.length === 0) {
      setErrorMsg("No changes to save.");
      return;
    }

    setStatus("saving");
    setErrorMsg("");
    try {
      const result = await applyEdits(jobId, edits);
      downloadBlob(result.blob, result.filename);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err.message || "Failed to save edits");
    }
  };

  const reset = () => {
    setJobId(null);
    setPages([]);
    setCurrentPage(0);
    setStatus("idle");
    setErrorMsg("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const page = pages[currentPage];
  const editedCount = pages.reduce(
    (sum, p) => sum + p.lines.filter((l) => l.text !== l.originalText).length,
    0
  );

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Text Editor</h1>
          <p className="text-sm text-gray-500">
            Click any line of text on the page to edit it directly.
          </p>
        </div>
        {jobId && (
          <button onClick={reset} className="text-sm text-gray-500 hover:text-gray-800 underline">
            Upload a different PDF
          </button>
        )}
      </header>

      {status === "idle" && (
        <div className="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center bg-white">
          <p className="text-gray-500 mb-4">Upload a PDF to start editing its text.</p>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleUpload}
            className="text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
          />
        </div>
      )}

      {status === "loading" && (
        <div className="text-center py-16 text-gray-500">Reading PDF…</div>
      )}

      {errorMsg && (
        <div className="bg-red-50 text-red-700 text-sm rounded-lg px-4 py-2 mb-4">{errorMsg}</div>
      )}

      {page && (status === "ready" || status === "saving") && (
        <div className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-3 text-sm">
            <button
              onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
              disabled={currentPage === 0}
              className="px-3 py-1 rounded-lg border disabled:opacity-40"
            >
              ← Prev
            </button>
            <span>
              Page {currentPage + 1} of {pages.length}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(pages.length - 1, p + 1))}
              disabled={currentPage === pages.length - 1}
              className="px-3 py-1 rounded-lg border disabled:opacity-40"
            >
              Next →
            </button>
          </div>

          <div
            className="relative bg-white shadow border overflow-auto max-w-full"
            style={{
              width: Math.round(page.width * PT_TO_PX),
              height: Math.round(page.height * PT_TO_PX),
            }}
          >
            <img
              src={pageImageUrl(jobId, currentPage, DPI)}
              alt={`Page ${currentPage + 1}`}
              width={Math.round(page.width * PT_TO_PX)}
              height={Math.round(page.height * PT_TO_PX)}
              className="absolute top-0 left-0 select-none pointer-events-none"
              draggable={false}
            />

            {page.lines.map((line) => {
              const [x0, y0, x1, y1] = line.bbox;
              const left = x0 * PT_TO_PX;
              const top = y0 * PT_TO_PX;
              const width = (x1 - x0) * PT_TO_PX;
              const height = (y1 - y0) * PT_TO_PX;
              const isEdited = line.text !== line.originalText;
              const isActive = activeLineId === line.id;

              return (
                <textarea
                  key={line.id}
                  value={line.text}
                  onFocus={() => setActiveLineId(line.id)}
                  onBlur={() => setActiveLineId(null)}
                  onChange={(e) => updateLineText(currentPage, line.id, e.target.value)}
                  className={`absolute resize-none overflow-hidden bg-transparent leading-none border
                    ${isActive ? "border-indigo-500 bg-white" : isEdited ? "border-amber-400 bg-amber-50/40" : "border-transparent hover:border-gray-300"}
                  `}
                  style={{
                    left,
                    top: top - 2,
                    width: Math.max(width, 20),
                    height: Math.max(height + 4, 14),
                    fontSize: Math.max(line.size * PT_TO_PX * 0.92, 8),
                    fontFamily: line.font.toLowerCase().includes("times")
                      ? "Georgia, serif"
                      : line.font.toLowerCase().includes("courier")
                      ? "monospace"
                      : "Arial, sans-serif",
                    color: `#${line.color.toString(16).padStart(6, "0")}`,
                    padding: 0,
                  }}
                />
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={status === "saving" || editedCount === 0}
              className="bg-indigo-600 disabled:bg-gray-300 text-white rounded-lg px-5 py-2 text-sm font-medium hover:bg-indigo-700 transition"
            >
              {status === "saving" ? "Saving…" : `Save & Download${editedCount ? ` (${editedCount} change${editedCount > 1 ? "s" : ""})` : ""}`}
            </button>
            <span className="text-xs text-gray-400">
              Amber boxes mark edited lines. Original file is deleted after you save.
            </span>
          </div>
        </div>
      )}
    </main>
  );
}
