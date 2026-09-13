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
      <h4 className="font-semibold mb-4 text-gray-800">Candidate Comparison</h4>

      <div className="space-y-3">
        {validCandidates.map((candidate) => (
          <div
            key={candidate.candidate_id}
            className={`border-2 rounded-lg p-4 transition-all ${
              candidate.accepted
                ? "bg-amber-50 border-amber-400 shadow-lg shadow-amber-200"
                : candidate.tests_passed === false
                ? "bg-red-50 border-red-200"
                : "bg-gray-50 border-gray-200"
            }`}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-semibold text-gray-800">{candidate.strategy}</div>
                  {candidate.accepted && (
                    <div className="inline-flex items-center gap-1 bg-amber-400 text-amber-900 px-2.5 py-0.5 rounded-full text-xs font-bold animate-pulse">
                      🏆 WINNER
                    </div>
                  )}
                </div>
                <div className="text-sm text-gray-700 mt-1">{candidate.explanation}</div>
              </div>
              <div className="text-right ml-4">
                {candidate.tests_passed === false ? (
                  <div className="text-xs bg-red-100 text-red-700 px-3 py-1 rounded font-medium">
                    Tests Failed
                  </div>
                ) : (
                  <div>
                    <div
                      className={`text-3xl font-bold ${
                        candidate.accepted ? "text-amber-600" : "text-blue-600"
                      }`}
                    >
                      {(candidate.speedup || 0).toFixed(2)}x
                    </div>
                    <div className="text-xs text-gray-600 mt-1">speedup</div>
                  </div>
                )}
              </div>
            </div>

            {candidate.benchmark_before_ms && candidate.benchmark_after_ms && (
              <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap gap-3 text-xs">
                <div className="bg-white px-2.5 py-1.5 rounded border border-gray-200">
                  <span className="text-gray-600">Before:</span>
                  <span className="font-mono font-semibold ml-2 text-gray-800">
                    {(candidate.benchmark_before_ms / 1000).toFixed(2)}s
                  </span>
                </div>
                <span className="text-gray-400 flex items-center">→</span>
                <div className="bg-white px-2.5 py-1.5 rounded border border-gray-200">
                  <span className="text-gray-600">After:</span>
                  <span className="font-mono font-semibold ml-2 text-gray-800">
                    {(candidate.benchmark_after_ms / 1000).toFixed(2)}s
                  </span>
                </div>
              </div>
            )}

            {candidate.rejection_reason && (
              <div className="mt-3 pt-3 border-t border-red-200">
                <div className="text-xs text-red-700 font-medium">
                  ❌ Rejected: {candidate.rejection_reason}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
