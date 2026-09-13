"use client";

import { OptimizationPass } from "../types";

export function PassCard({ pass }: { pass: OptimizationPass }) {
  const speedupPercent = ((pass.speedup - 1) * 100).toFixed(1);

  return (
    <div className="border border-gray-200 rounded-lg p-6 mb-6 bg-white">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold">Pass {pass.pass}</h3>
          <p className="text-sm text-gray-700 mt-1">
            Optimized: <code className="bg-gray-100 px-2 py-1 rounded">{pass.hotspot.function}</code>
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-green-600">{pass.speedup.toFixed(1)}x</div>
          <div className="text-sm text-gray-600">speedup</div>
          <div className="text-xs text-green-600 mt-1">+{speedupPercent}%</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-red-50 p-3 rounded">
          <div className="text-xs text-gray-700">Before</div>
          <div className="font-semibold text-sm">{(pass.before_ms / 1000).toFixed(2)}s</div>
        </div>
        <div className="flex items-center justify-center">
          <div className="text-gray-400">→</div>
        </div>
        <div className="bg-green-50 p-3 rounded">
          <div className="text-xs text-gray-700">After</div>
          <div className="font-semibold text-sm">{(pass.after_ms / 1000).toFixed(2)}s</div>
        </div>
      </div>

      <div className="bg-gray-50 p-3 rounded text-sm">
        <div className="text-gray-800 mb-1 font-medium">Hotspot Details</div>
        <div className="text-xs text-gray-800">
          <div>📁 {pass.hotspot.file}:{pass.hotspot.line}</div>
          <div>📞 Calls: {pass.hotspot.calls.toLocaleString()}</div>
          <div>⏱️ Runtime: {pass.hotspot.runtime_percent.toFixed(1)}%</div>
        </div>
      </div>

      {pass.winner && (
        <div className="mt-4 pt-4 border-t">
          <div className="text-sm font-semibold mb-2">✨ Winner: {pass.winner.strategy}</div>
          <div className="text-xs text-gray-800">{pass.winner.explanation}</div>
          {pass.winner.files_changed && (
            <div className="mt-2 text-xs">
              <div className="text-gray-800 font-medium">Files changed:</div>
              {pass.winner.files_changed.map((file) => (
                <div key={file} className="bg-gray-100 px-2 py-1 rounded mt-1 font-mono">
                  {file}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
