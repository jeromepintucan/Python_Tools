"use client";

import Link from "next/link";
import ToolCard from "../components/ToolCard";
import {
  mergePdfs,
  splitPdf,
  compressPdf,
  rotatePdf,
  deletePages,
  pdfToImages,
} from "../lib/api";

export default function Home() {
  return (
    <main className="max-w-5xl mx-auto px-4 py-10">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">PDF Editor</h1>
        <p className="text-gray-500 mt-1">
          Free PDF tools. Files are processed and then automatically deleted —
          nothing is kept on the server.
        </p>
      </header>

      <Link
        href="/editor"
        className="block mb-8 rounded-xl border border-indigo-200 bg-indigo-50 hover:bg-indigo-100 transition p-5"
      >
        <h2 className="font-semibold text-indigo-900">✏️ Edit text in a PDF</h2>
        <p className="text-sm text-indigo-700">
          Click directly on any line of text and change it, in place.
        </p>
      </Link>

      <div className="grid sm:grid-cols-2 gap-5">
        <ToolCard
          title="Merge"
          description="Combine multiple PDFs into one, in the order you select them."
          multiple
          onRun={(files) => mergePdfs(files)}
        />

        <ToolCard
          title="Split"
          description='Split a PDF into parts by page range, e.g. "1-3,4-6,7".'
          extraFields={[
            { name: "ranges", label: "Page ranges", type: "text", placeholder: "1-3,4-6,7" },
          ]}
          onRun={(file, fields) => splitPdf(file, fields.ranges || "1")}
        />

        <ToolCard
          title="Compress"
          description="Reduce file size while keeping the PDF usable."
          extraFields={[
            {
              name: "quality",
              label: "Quality",
              type: "select",
              options: ["low", "medium", "high"],
              default: "medium",
            },
          ]}
          onRun={(file, fields) => compressPdf(file, fields.quality || "medium")}
        />

        <ToolCard
          title="Rotate"
          description="Rotate all or specific pages by 90/180/270 degrees."
          extraFields={[
            {
              name: "degrees",
              label: "Degrees",
              type: "select",
              options: ["90", "180", "270"],
              default: "90",
            },
            { name: "pages", label: "Pages (or 'all')", type: "text", placeholder: "all" },
          ]}
          onRun={(file, fields) =>
            rotatePdf(file, parseInt(fields.degrees || "90", 10), fields.pages || "all")
          }
        />

        <ToolCard
          title="Delete pages"
          description='Remove specific pages, e.g. "2,4,7".'
          extraFields={[
            { name: "pages", label: "Pages to delete", type: "text", placeholder: "2,4,7" },
          ]}
          onRun={(file, fields) => deletePages(file, fields.pages || "")}
        />

        <ToolCard
          title="PDF to images"
          description="Convert each page to a PNG, delivered as a zip."
          extraFields={[
            { name: "dpi", label: "DPI", type: "text", placeholder: "150", default: "150" },
          ]}
          onRun={(file, fields) => pdfToImages(file, parseInt(fields.dpi || "150", 10))}
        />
      </div>

      <footer className="mt-10 text-xs text-gray-400">
        Runs against your own backend instance. No accounts, no tracking, no stored files.
      </footer>
    </main>
  );
}
