/**
 * Type definitions for Optimizer results.
 * Matches the data structure the CLI will export as JSON.
 */

export interface Hotspot {
  function: string;
  qualified_name: string;
  file: string;
  line: number;
  calls: number;
  self_time: number;
  cumulative_time: number;
  runtime_percent: number;
}

export interface Candidate {
  candidate_id: string;
  strategy: string;
  explanation: string;
  files_changed: string[];
  tests_passed?: boolean;
  benchmark_before_ms?: number;
  benchmark_after_ms?: number;
  speedup?: number;
  accepted: boolean;
  rejection_reason?: string;
}

export interface OptimizationPass {
  pass: number;
  hotspot: Hotspot;
  candidates: Candidate[];
  winner?: Candidate;
  before_ms: number;
  after_ms: number;
  speedup: number;
}

export interface OptimizationResult {
  repository: string;
  timestamp: string;
  workload_command: string;
  test_command?: string;
  total_speedup: number;
  passes: OptimizationPass[];
}
