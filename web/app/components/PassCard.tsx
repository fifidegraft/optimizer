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
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-rose-50 p-3 rounded border border-rose-200">
            <div className="text-xs text-gray-700">Before</div>
            <div className="font-semibold text-sm text-gray-800">
              {(pass.before_ms / 1000).toFixed(2)}s
            </div>
          </div>
          <div className="flex items-center justify-center">
            <div className="text-gray-400 font-bold">→</div>
          </div>
          <div className="bg-emerald-50 p-3 rounded border border-emerald-200">
            <div className="text-xs text-gray-700">After</div>
            <div className="font-semibold text-sm text-gray-800">
              {(pass.after_ms / 1000).toFixed(2)}s
            </div>
          </div>
        </div>
      </div>

      {/* Hotspot Details */}
      <div className="px-6 py-4 border-b border-gray-200">
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
        <div className="px-6 py-4 bg-amber-50 border-t border-amber-200">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">🏆</span>
            <div className="text-sm font-bold text-amber-900 uppercase tracking-wide">
              Winning Optimization
            </div>
          </div>
          <div className="bg-white rounded border border-amber-200 p-3">
            <div className="font-semibold text-gray-800 mb-1">
              {pass.winner.strategy}
            </div>
            <div className="text-sm text-gray-700 mb-3">{pass.winner.explanation}</div>
            {pass.winner.files_changed && (
              <div className="text-xs">
                <div className="text-gray-700 font-medium mb-2">Files Modified:</div>
                <div className="space-y-1">
                  {pass.winner.files_changed.map((file) => (
                    <div
                      key={file}
                      className="bg-gray-50 px-2 py-1 rounded font-mono text-gray-800 border border-gray-200"
                    >
                      📝 {file}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
