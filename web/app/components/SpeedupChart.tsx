"use client";

import { OptimizationPass } from "../types";

interface SpeedupChartProps {
  passes: OptimizationPass[];
}

export function SpeedupChart({ passes }: SpeedupChartProps) {
  // Calculate cumulative speedup
  let cumulativeSpeedup = 1;
  const chartData = passes.map((pass) => {
    cumulativeSpeedup *= pass.speedup;
    return {
      pass: pass.pass,
      individual: pass.speedup,
      cumulative: cumulativeSpeedup,
    };
  });

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
      <h3 className="text-lg font-semibold mb-6">Speedup Progression</h3>

      <div>
        {/* Time Comparison Table */}
        <div>
          <div className="text-sm font-medium text-gray-800 mb-4">
            Pass Details
          </div>

          <div className="space-y-3">
            {passes.map((pass) => (
              <div
                key={pass.pass}
                className="border border-gray-200 rounded p-3 bg-gray-50"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium text-gray-800">Pass {pass.pass}</div>
                  <div className="text-sm font-bold text-green-600">
                    {pass.speedup.toFixed(2)}x
                  </div>
                </div>

                {/* Time bars */}
                <div className="space-y-1">
                  <div className="text-xs text-gray-700 mb-1">Before</div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-6 bg-rose-100 rounded flex items-center px-2">
                      <div
                        className="h-full bg-rose-400 rounded flex items-center justify-center text-white text-xs font-semibold"
                        style={{
                          width: "100%",
                        }}
                      >
                        {(pass.before_ms / 1000).toFixed(2)}s
                      </div>
                    </div>
                  </div>

                  <div className="text-xs text-gray-700 mt-2 mb-1">After</div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-6 bg-emerald-100 rounded flex items-center px-2">
                      <div
                        className="h-full bg-emerald-400 rounded flex items-center justify-center text-white text-xs font-semibold"
                        style={{
                          width: `${(pass.after_ms / pass.before_ms) * 100}%`,
                        }}
                      >
                        {(pass.after_ms / 1000).toFixed(2)}s
                      </div>
                    </div>
                  </div>

                  <div className="text-xs text-emerald-700 font-medium mt-2">
                    ✨ Saved {(pass.before_ms - pass.after_ms).toLocaleString()}ms
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-green-50 p-3 rounded text-center">
            <div className="text-2xl font-bold text-green-600">
              {chartData[chartData.length - 1].cumulative.toFixed(2)}x
            </div>
            <div className="text-xs text-gray-700 mt-1">Total Speedup</div>
          </div>

          <div className="bg-blue-50 p-3 rounded text-center">
            <div className="text-2xl font-bold text-blue-600">{passes.length}</div>
            <div className="text-xs text-gray-700 mt-1">Passes</div>
          </div>

          <div className="bg-purple-50 p-3 rounded text-center">
            <div className="text-2xl font-bold text-purple-600">
              {(((chartData[chartData.length - 1].cumulative - 1) * 100)).toFixed(0)}%
            </div>
            <div className="text-xs text-gray-700 mt-1">Improvement</div>
          </div>
        </div>
      </div>
    </div>
  );
}
