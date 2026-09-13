"use client";

import { useState } from "react";
import { OptimizationResult } from "../types";

interface FileUploadProps {
  onLoad: (data: OptimizationResult) => void;
}

export function FileUpload({ onLoad }: FileUploadProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setLoading(true);
    setError(null);

    try {
      const text = await file.text();
      const data = JSON.parse(text) as OptimizationResult;
      onLoad(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to parse JSON file"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center bg-gray-50">
      <div className="mb-4">
        <div className="text-5xl mb-2">📂</div>
        <h3 className="text-lg font-semibold mb-1">Upload Optimizer Results</h3>
        <p className="text-sm text-gray-600">
          Load a JSON results file from the CLI to view optimization reports
        </p>
      </div>

      <input
        type="file"
        accept=".json"
        onChange={(e) => {
          if (e.target.files?.[0]) {
            handleFile(e.target.files[0]);
          }
        }}
        disabled={loading}
        className="hidden"
        id="file-input"
      />

      <label
        htmlFor="file-input"
        className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg cursor-pointer font-medium transition"
      >
        {loading ? "Loading..." : "Choose File"}
      </label>

      {error && <div className="mt-4 text-sm text-red-600">❌ {error}</div>}

      <div className="mt-4 text-xs text-gray-500">
        <div>Generate with: <code className="bg-gray-200 px-2 py-1 rounded">python -m optimizer run demo --json &gt; results.json</code></div>
      </div>
    </div>
  );
}
