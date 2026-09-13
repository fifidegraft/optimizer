"use client";

import { useState } from "react";
import { OptimizationResult } from "./types";
import { FileUpload } from "./components/FileUpload";
import { ResultsSummary } from "./components/ResultsSummary";
import { PassCard } from "./components/PassCard";
import { CandidateComparison } from "./components/CandidateComparison";

const MOCK_RESULT: OptimizationResult = {
  repository: "demo",
  timestamp: new Date().toISOString(),
  workload_command: "python scripts/performance_scenario.py",
  test_command: "pytest -q",
  total_speedup: 8.5,
  passes: [
    {
      pass: 1,
      hotspot: {
        function: "parse_record",
        qualified_name: "app.parsing.parse_record",
        file: "demo/app/parsing.py",
        line: 15,
        calls: 5000,
        self_time: 2.34,
        cumulative_time: 2.45,
        runtime_percent: 65.0,
      },
      candidates: [
        {
          candidate_id: "candidate_a",
          strategy: "Cache parsed records",
          explanation: "Move regex compilation outside the loop to avoid recompiling the same pattern",
          files_changed: ["demo/app/parsing.py"],
          tests_passed: true,
          benchmark_before_ms: 5000,
          benchmark_after_ms: 1200,
          speedup: 4.17,
          accepted: true,
        },
        {
          candidate_id: "candidate_b",
          strategy: "Use compiled regex module",
          explanation: "Pre-compile regex patterns at module load time",
          files_changed: ["demo/app/parsing.py"],
          tests_passed: true,
          benchmark_before_ms: 5000,
          benchmark_after_ms: 2800,
          speedup: 1.79,
          accepted: false,
        },
      ],
      winner: {
        candidate_id: "candidate_a",
        strategy: "Cache parsed records",
        explanation: "Move regex compilation outside the loop",
        files_changed: ["demo/app/parsing.py"],
        tests_passed: true,
        benchmark_before_ms: 5000,
        benchmark_after_ms: 1200,
        speedup: 4.17,
        accepted: true,
      },
      before_ms: 5000,
      after_ms: 1200,
      speedup: 4.17,
    },
    {
      pass: 2,
      hotspot: {
        function: "get_user",
        qualified_name: "app.users.get_user",
        file: "demo/app/users.py",
        line: 28,
        calls: 3000,
        self_time: 1.85,
        cumulative_time: 2.12,
        runtime_percent: 45.0,
      },
      candidates: [
        {
          candidate_id: "candidate_c",
          strategy: "Add user lookup cache",
          explanation: "Cache user lookups in memory to avoid repeated table scans",
          files_changed: ["demo/app/users.py", "demo/app/__init__.py"],
          tests_passed: true,
          benchmark_before_ms: 1200,
          benchmark_after_ms: 141,
          speedup: 8.5,
          accepted: true,
        },
      ],
      winner: {
        candidate_id: "candidate_c",
        strategy: "Add user lookup cache",
        explanation: "Cache user lookups in memory",
        files_changed: ["demo/app/users.py"],
        tests_passed: true,
        benchmark_before_ms: 1200,
        benchmark_after_ms: 141,
        speedup: 8.5,
        accepted: true,
      },
      before_ms: 1200,
      after_ms: 141,
      speedup: 8.5,
    },
  ],
};

export default function Home() {
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [showMock, setShowMock] = useState(false);

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">⚡ Optimizer Results</h1>
          <p className="text-gray-700">AI proposes. The runtime decides.</p>
        </div>

        {/* Content */}
        {!result ? (
          <div>
            <FileUpload onLoad={setResult} />

            {/* Demo Button */}
            <div className="mt-6 text-center">
              <button
                onClick={() => {
                  setResult(MOCK_RESULT);
                  setShowMock(true);
                }}
                className="text-sm text-blue-600 hover:text-blue-700 underline"
              >
                Or view demo results
              </button>
            </div>
          </div>
        ) : (
          <div>
            {showMock && (
              <div className="mb-6 p-4 bg-blue-50 border border-blue-300 rounded-lg text-sm text-blue-900">
                👀 Showing mock demo results. Upload your own results.json to see real optimization data.
              </div>
            )}

            <ResultsSummary result={result} />

            <div className="space-y-6">
              {result.passes.map((pass) => (
                <div key={pass.pass}>
                  <PassCard pass={pass} />
                  <CandidateComparison candidates={pass.candidates} />
                </div>
              ))}
            </div>

            <button
              onClick={() => {
                setResult(null);
                setShowMock(false);
              }}
              className="mt-8 text-sm text-gray-700 hover:text-gray-900 underline"
            >
              ← Load different results
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
