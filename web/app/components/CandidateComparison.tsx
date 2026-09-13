"use client";

import { Candidate } from "../types";

interface CandidateComparisonProps {
  candidates: Candidate[];
}

export function CandidateComparison({ candidates }: CandidateComparisonProps) {
  const validCandidates = candidates.filter((c) => c.speedup !== undefined);

  if (validCandidates.length === 0) {
    return null;
  }

  const fastest = validCandidates.reduce((a, b) =>
    (b.speedup || 0) > (a.speedup || 0) ? b : a
  );

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
      <h4 className="font-semibold mb-4">Candidate Comparison</h4>

      <div className="space-y-3">
        {validCandidates.map((candidate) => (
          <div
            key={candidate.candidate_id}
            className={`border rounded-lg p-4 ${
              candidate.accepted ? "bg-green-50 border-green-200" : "bg-gray-50 border-gray-200"
            }`}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="font-medium">{candidate.strategy}</div>
                <div className="text-sm text-gray-800 mt-1">{candidate.explanation}</div>
              </div>
              <div className="text-right">
                {candidate.tests_passed === false ? (
                  <div className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded">
                    Tests Failed
                  </div>
                ) : (
                  <div className="text-2xl font-bold text-blue-600">
                    {(candidate.speedup || 0).toFixed(2)}x
                  </div>
                )}
              </div>
            </div>

            {candidate.benchmark_before_ms && candidate.benchmark_after_ms && (
              <div className="mt-3 flex gap-2 text-xs">
                <div>
                  <span className="text-gray-800">Before:</span>
                  <span className="font-mono ml-1">{(candidate.benchmark_before_ms / 1000).toFixed(2)}s</span>
                </div>
                <span className="text-gray-400">→</span>
                <div>
                  <span className="text-gray-800">After:</span>
                  <span className="font-mono ml-1">{(candidate.benchmark_after_ms / 1000).toFixed(2)}s</span>
                </div>
              </div>
            )}

            {candidate.rejection_reason && (
              <div className="mt-2 text-xs text-red-600">❌ Rejected: {candidate.rejection_reason}</div>
            )}

            {candidate.accepted && (
              <div className="mt-2 text-xs text-green-600">✅ Accepted as winner</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
