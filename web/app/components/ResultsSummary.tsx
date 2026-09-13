"use client";

import { OptimizationResult } from "../types";

export function ResultsSummary({ result }: { result: OptimizationResult }) {
  const totalImprovement = ((result.total_speedup - 1) * 100).toFixed(1);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      <div className="bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-lg p-6">
        <div className="text-sm text-gray-800 mb-1">Overall Speedup</div>
        <div className="text-4xl font-bold text-green-600">{result.total_speedup.toFixed(2)}x</div>
        <div className="text-xs text-green-700 mt-2">+{totalImprovement}% faster</div>
      </div>

      <div className="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-lg p-6">
        <div className="text-sm text-gray-800 mb-1">Passes Completed</div>
        <div className="text-4xl font-bold text-blue-600">{result.passes.length}</div>
        <div className="text-xs text-blue-700 mt-2">{result.passes.length} bottleneck{result.passes.length > 1 ? "s" : ""} fixed</div>
      </div>

      <div className="bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200 rounded-lg p-6">
        <div className="text-sm text-gray-800 mb-1">Repository</div>
        <div className="font-semibold text-purple-900 truncate">{result.repository}</div>
        <div className="text-xs text-purple-700 mt-2">
          {new Date(result.timestamp).toLocaleDateString()}
        </div>
      </div>
    </div>
  );
}
