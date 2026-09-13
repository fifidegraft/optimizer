"use client";

import { OptimizationPass } from "../types";

export function PassCard({ pass }: { pass: OptimizationPass }) {
  const speedupPercent = ((pass.speedup - 1) * 100).toFixed(1);

  return (
    <div className="border border-gray-300 rounded-lg overflow-hidden bg-white mb-8">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-50 to-blue-100 px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-blue-900 uppercase tracking-wide">
              Pass {pass.pass}
            </div>
            <p className="text-gray-700 mt-1">
              Optimized: <code className="bg-white px-2 py-0.5 rounded border border-gray-200 font-semibold">
                {pass.hotspot.function}
              </code>
            </p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold text-green-600">{pass.speedup.toFixed(1)}x</div>
            <div className="text-xs text-gray-600 mt-0.5">faster</div>
            <div className="text-xs text-green-700 font-semibold mt-1">+{speedupPercent}%</div>
          </div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-3">
          📊 Performance Metrics
        </div>
        <div className="grid grid-cols-3 gap-3 items-stretch">
          <div className="bg-rose-50 p-3 rounded border border-rose-200 flex flex-col justify-center">
            <div className="text-xs text-gray-700">Before</div>
            <div className="font-semibold text-sm text-gray-800">
              {(pass.before_ms / 1000).toFixed(2)}s
            </div>
          </div>
          <div className="flex items-center justify-center">
            <div className="text-5xl text-gray-400 font-bold leading-none">→</div>
          </div>
          <div className="bg-emerald-50 p-3 rounded border border-emerald-200 flex flex-col justify-center">
            <div className="text-xs text-gray-700">After</div>
            <div className="font-semibold text-sm text-gray-800">
              {(pass.after_ms / 1000).toFixed(2)}s
            </div>
          </div>
        </div>
      </div>

      {/* Details Block - Hotspot & Winner Combined */}
      <div className="px-6 py-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Hotspot Details */}
          <div>
            <div className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-3">
              🔍 Hotspot Details
            </div>
            <div className="bg-gray-50 p-3 rounded border border-gray-200">
              <div className="text-xs text-gray-700 space-y-2">
                <div className="flex justify-between">
                  <span>📁 File:</span>
                  <code className="font-mono text-gray-800">{pass.hotspot.file}:{pass.hotspot.line}</code>
                </div>
                <div className="flex justify-between">
                  <span>📞 Calls:</span>
                  <span className="font-semibold text-gray-800">{pass.hotspot.calls.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>⏱️ Runtime Impact:</span>
                  <span className="font-semibold text-gray-800">{pass.hotspot.runtime_percent.toFixed(1)}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Winner Section */}
          {pass.winner && (
            <div className="bg-amber-50 p-3 rounded border border-amber-200">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-2xl">🏆</span>
                <div className="text-xs font-bold text-amber-900 uppercase tracking-wide">
                  Winning Optimization
                </div>
              </div>
              <div className="font-semibold text-sm text-gray-800 mb-1">
                {pass.winner.strategy}
              </div>
              <div className="text-xs text-gray-700 mb-3">{pass.winner.explanation}</div>
              {pass.winner.files_changed && (
                <div className="text-xs">
                  <div className="text-gray-700 font-medium mb-2">Files Modified:</div>
                  <div className="space-y-1">
                    {pass.winner.files_changed.map((file) => (
                      <div
                        key={file}
                        className="bg-white px-2 py-1 rounded font-mono text-gray-700 text-xs border border-gray-200"
                      >
                        📝 {file}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Candidate Evaluation */}
      {pass.candidates && pass.candidates.length > 0 && (
        <div className="px-6 py-4 border-t border-gray-200">
          <div className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-4">
            📊 Candidate Evaluation
          </div>
          <div className="space-y-3">
            {pass.candidates.map((candidate) => {
              const fastest = pass.candidates.reduce((a, b) =>
                (b.speedup || 0) > (a.speedup || 0) ? b : a
              );
              return (
                <div
                  key={candidate.candidate_id}
                  className={`border rounded-lg p-3 transition-all ${
                    candidate.accepted
                      ? "bg-amber-50 border-amber-400 shadow-md shadow-amber-200"
                      : candidate.tests_passed === false
                      ? "bg-red-50 border-red-200"
                      : "bg-gray-50 border-gray-200"
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <div className="font-semibold text-sm text-gray-800">{candidate.strategy}</div>
                        {candidate.accepted && (
                          <div className="inline-flex items-center gap-1 bg-amber-400 text-amber-900 px-2 py-0.5 rounded-full text-xs font-bold animate-pulse">
                            🏆 WINNER
                          </div>
                        )}
                      </div>
                      <div className="text-xs text-gray-700">{candidate.explanation}</div>
                    </div>
                    <div className="text-right ml-4">
                      {candidate.tests_passed === false ? (
                        <div className="text-xs bg-red-100 text-red-700 px-2.5 py-1 rounded font-medium">
                          Tests Failed
                        </div>
                      ) : (
                        <div>
                          <div
                            className={`text-2xl font-bold ${
                              candidate.accepted ? "text-amber-600" : "text-blue-600"
                            }`}
                          >
                            {(candidate.speedup || 0).toFixed(2)}x
                          </div>
                          <div className="text-xs text-gray-600">speedup</div>
                        </div>
                      )}
                    </div>
                  </div>

                  {candidate.benchmark_before_ms && candidate.benchmark_after_ms && (
                    <div className="mt-2 pt-2 border-t border-gray-200 flex flex-wrap gap-2 text-xs">
                      <div className="bg-white px-2 py-1 rounded border border-gray-200">
                        <span className="text-gray-600">Before:</span>
                        <span className="font-mono font-semibold ml-1 text-gray-800">
                          {(candidate.benchmark_before_ms / 1000).toFixed(2)}s
                        </span>
                      </div>
                      <span className="text-gray-400 flex items-center">→</span>
                      <div className="bg-white px-2 py-1 rounded border border-gray-200">
                        <span className="text-gray-600">After:</span>
                        <span className="font-mono font-semibold ml-1 text-gray-800">
                          {(candidate.benchmark_after_ms / 1000).toFixed(2)}s
                        </span>
                      </div>
                    </div>
                  )}

                  {candidate.rejection_reason && (
                    <div className="mt-2 pt-2 border-t border-red-200">
                      <div className="text-xs text-red-700 font-medium">
                        ❌ Rejected: {candidate.rejection_reason}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
