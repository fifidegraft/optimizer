# Optimizer

**Autonomous performance engineer for Python codebases.**

> AI proposes. The runtime decides.

```bash
optimizer run . \
  --workload "python scripts/performance_scenario.py" \
  --test "pytest -q" \
  --passes 3
```

- `.` is the optimization target: the entire repository.
- `--workload` specifies how to exercise the application so Optimizer can collect runtime
  measurements. It does not restrict optimization to that file. Optimizer profiles whatever
  code the workload touches across the repo.
- `--test` verifies behavior. Candidates that fail it are rejected.
- `--passes` is how many bottlenecks to fix in sequence, re-profiling after each.

## What it does

```
PROFILE
   ↓
MAP PROJECT + EXECUTION PATHS
   ↓
IDENTIFY HOTSPOT
   ↓
TRACE RELATED FUNCTIONS ACROSS FILES
   ↓
GENERATE MULTIPLE CANDIDATE OPTIMIZATIONS
   ↓
RUN TESTS
   ↓
BENCHMARK EACH CANDIDATE
   ↓
KEEP FASTEST VALID CHANGE
   ↓
RE-PROFILE
   ↓
REPEAT
```

The LLM is one component. The value is measurement + repository context + experimentation
+ verification. The LLM never gets to declare code better; the profiler, the test suite, and
the benchmark decide.

The full brief, including scope, optimization classes, the safety model, the demo script,
and the hour-by-hour plan, is in [`docs/project_brief.md`](docs/project_brief.md). Read it.

## Team

Four people, four modules. Each module is yours end to end: design, code, tests, and the
interface you expose to the others. Put your name in the table and go.

| Folder | Owner | Responsibility |
|---|---|---|
| `optimizer/scanner/` | | **Repository Intelligence.** Find `.py` files (ignore `.git`, `.venv`, `build`, `dist`, ...), parse ASTs, extract functions, classes, imports and calls, build a call/dependency graph, and provide the related code context around a hotspot. |
| `optimizer/profiler/` | | **Performance Engine.** Run the workload command, integrate `cProfile`, parse the output, rank the hottest functions, record baseline timings, benchmark modified candidates, re-profile after accepted changes. |
| `optimizer/agent/` | | **Optimization Agent.** Gather the hotspot plus dependency context, build the LLM prompt, generate 2–3 candidate optimizations that preserve behavior, return structured patches touching 1–3 files, explain each strategy. |
| `optimizer/verifier/` | | **Safety, CLI, and Developer Experience.** CLI commands, run the tests, detect failures, back up files, roll back failed candidates, render git-style diffs, report before/after metrics, polish terminal output, own the demo. |
| `optimizer/models/` | everyone | **Shared representation.** The hotspot and candidate objects every module passes around. Agree on these in hour 0 (see brief §9 and §11) before anyone writes module code. |
| `demo/` | everyone | **Demo repository.** A small deterministic Python project with 15–30 functions, three planted bottlenecks, tests, and a workload script (brief §21). |
| `web/` | | **Results display (extension).** A Next.js app for showing what Optimizer found and how much it sped things up. Only if the CLI is done. |

Rules that keep four parallel tracks from colliding:

- One optimization touches **1–3 related files**. Optimizer analyzes the whole repo; it edits a little of it.
- Modules communicate with **plain Python objects or dicts** matching `optimizer/models/`.
- Lock the integration contract in hour 0. Do not wait until the end to integrate.
- Every candidate change goes: back up → apply → tests → benchmark → keep or roll back.

## Milestones

| When | Must have |
|---|---|
| Hour 0–1 | Repo, shared schema, demo project, CLI commands agreed, branches set up. |
| Hour 4 | `repo → scanner → profiler → hotspot object` works on `demo/`. |
| Hour 7 | `hotspot → context → LLM → candidate patch → apply` works. |
| Hour 9 | `candidate → tests → benchmark → rollback / accept`, best of 3. |
| Hour 10 | Git-style diff, performance summary, multi-pass if stable. |
| Hour 11–12 | Rehearse the demo. Fix integration bugs. Add nothing new. |

Priority if time gets tight: P0 is the end-to-end loop with one candidate; P1 is
whole-repo mapping, cross-file context, multiple candidates, diff; P2 is multi-pass,
richer scoring, terminal polish, the web display. Details in brief §26.

## Definition of success

Point Optimizer at a multi-file Python project, profile it, find a real measured
bottleneck, trace it across files, generate several fixes, test and benchmark each,
reject the broken or slower ones, apply the fastest valid one, and show a clear speedup.
One convincing end-to-end demo, not every repository.

## Working agreements

- Branch per person off `main`; small PRs, merged often.
- Python 3.11+. Tooling, packaging, and dependencies are decided together in hour 0.
- Never commit API keys. Use a local `.env`.
