"use client";

import { useState } from "react";
import { downloadBlob } from "../lib/api";

export default function ToolCard({ title, description, multiple, extraFields, onRun }) {
  const [files, setFiles] = useState([]);
  const [fieldValues, setFieldValues] = useState({});
  const [status, setStatus] = useState("idle"); // idle | working | done | error
  const [errorMsg, setErrorMsg] = useState("");

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
    setStatus("idle");
  };

  const handleFieldChange = (name, value) => {
    setFieldValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleRun = async () => {
    if (files.length === 0) return;
    setStatus("working");
    setErrorMsg("");
    try {
      const result = await onRun(multiple ? files : files[0], fieldValues);
      downloadBlob(result.blob, result.filename);
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err.message || "Something went wrong");
    }
  };

  return (
    <div className="border border-gray-200 rounded-xl p-5 bg-white shadow-sm flex flex-col gap-3">
      <div>
        <h3 className="font-semibold text-lg">{title}</h3>
        <p className="text-sm text-gray-500">{description}</p>
      </div>

      <input
        type="file"
        accept="application/pdf"
        multiple={multiple}
        onChange={handleFileChange}
        className="text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
      />

      {extraFields?.map((field) => (
        <div key={field.name} className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-600">{field.label}</label>
          {field.type === "select" ? (
            <select
              className="border rounded-lg px-2 py-1 text-sm"
              defaultValue={field.default}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
            >
              {field.options.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              placeholder={field.placeholder}
              defaultValue={field.default}
              className="border rounded-lg px-2 py-1 text-sm"
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
            />
          )}
        </div>
      ))}

      <button
        onClick={handleRun}
        disabled={files.length === 0 || status === "working"}
        className="mt-1 bg-indigo-600 disabled:bg-gray-300 text-white rounded-lg py-2 text-sm font-medium hover:bg-indigo-700 transition"
      >
        {status === "working" ? "Processing…" : "Run"}
      </button>

      {status === "done" && (
        <p className="text-xs text-green-600">Done — check your downloads.</p>
      )}
      {status === "error" && <p className="text-xs text-red-600">{errorMsg}</p>}
    </div>
  );
}
