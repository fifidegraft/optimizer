# Optimizer — Hackathon Project Brief

## 1. One-line idea

**Optimizer is an autonomous performance engineer for Python codebases.**

A developer runs:

```bash
optimizer .
```

Optimizer profiles the project, finds measured performance bottlenecks, generates multiple refactoring candidates, runs the project tests, benchmarks each candidate, rejects regressions, applies the fastest valid improvement, and then re-profiles the project to find the next bottleneck.

> **AI proposes. The runtime decides.**

---

## 2. Why this is different from pasting code into ChatGPT

The product is **not** just "ask an LLM to make this code faster."

A normal AI prompt:
1. Reads whatever code the user pastes.
2. Guesses what looks inefficient.
3. Suggests a rewrite.
4. Does not know whether the rewrite is actually faster.
5. Does not understand the whole project execution path.
6. Does not automatically validate behavior.

Optimizer instead:

```text
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

The LLM is only one component.

The actual value is:

**measurement + repository context + experimentation + verification**

---

## 3. Hackathon scope

### We WILL build

- Python-only support
- Whole-repository scanning
- Function and import mapping
- Runtime profiling
- Hotspot identification
- Cross-file context gathering
- LLM-generated optimization candidates
- 2–3 candidate implementations per optimization
- Automated test validation
- Before/after benchmarking
- Automatic rollback on failure
- Git-style diff output
- Multi-pass optimization
- CLI interface
- Project-level performance report

### We WILL NOT build

- Support for every programming language
- Arbitrary production-scale repositories
- Distributed systems optimization
- Frontend rendering optimization
- Full database query-plan optimization
- Memory optimization as a primary feature
- Large-scale automatic rewrites
- Guaranteed globally optimal code
- Fully automatic benchmark discovery for every project
- Modifications to dozens of files at once

### Important scope rule

Optimizer can **analyze the whole repository**, but one optimization should usually modify only:

**1–3 related files at a time.**

---

## 4. Target repository size for the demo

For the hackathon MVP:

- Python projects
- Roughly 5–50 source files
- Existing test suite preferred
- User supplies a benchmark/run command
- We optimize one hotspot at a time

Example:

```bash
optimizer . \
  --benchmark "python benchmark.py" \
  --test "pytest -q"
```

---

## 5. Core CLI experience

### Analyze only

```bash
optimizer inspect .
```

Example output:

```text
Optimizer

Scanning repository...
23 Python files found
61 functions indexed

Running benchmark...
Profiling execution...

Performance opportunities

HIGH
services/recommendations.py:41
generate_feed()

62% of total runtime
10,420 calls

Related execution path:
recommendations.generate_feed()
    ↓
users.get_user()
    ↓
database.find_user()

Likely issue:
Repeated database/user lookup inside loop

Affected files:
- services/recommendations.py
- services/users.py
- database.py
```

---

### Optimize

```bash
optimizer run . \
  --benchmark "python benchmark.py" \
  --test "pytest -q"
```

Example output:

```text
Targeting:
services/recommendations.py::generate_feed

Baseline: 840 ms

Generating candidates...

Candidate A
Strategy: batch user retrieval
Runtime: 191 ms
Tests: 34/34 passed
Result: VALID

Candidate B
Strategy: local caching
Runtime: 303 ms
Tests: 34/34 passed
Result: VALID

Candidate C
Strategy: concurrent execution
Runtime: 417 ms
Tests: 32/34 passed
Result: REJECTED

Selected Candidate A

Before: 840 ms
After:  191 ms

Speedup: 4.4x
Runtime reduction: 77.3%

Files changed:
- services/recommendations.py
- services/users.py

Apply changes? [Y/n]
```

---

## 6. Multi-pass mode

After applying an optimization, Optimizer profiles the application again.

Example:

```text
PASS 1
database_lookup()
1.80 sec → 0.42 sec

Re-profiling...

PASS 2
parse_results()
0.53 sec → 0.18 sec

Re-profiling...

PASS 3
No additional high-impact optimization found.
```

Possible CLI:

```bash
optimizer run . --passes 3
```

The loop:

```text
PROFILE
  ↓
OPTIMIZE
  ↓
VERIFY
  ↓
BENCHMARK
  ↓
RE-PROFILE
  ↓
NEXT BOTTLENECK
```

---

## 7. Types of optimizations we should support

We do not need to solve every performance problem.

Focus on optimization classes that are:

1. Easy to demonstrate
2. Easy to benchmark
3. Relatively safe to validate
4. Common enough for the LLM to reason about well

### A. Poor lookup structures

Before:

```python
for user in users:
    if user.id in [x.user_id for x in purchases]:
        active.append(user)
```

After:

```python
purchased_user_ids = {x.user_id for x in purchases}

for user in users:
    if user.id in purchased_user_ids:
        active.append(user)
```

Typical improvement:

- repeated list scans → set/dict lookup
- O(n²)-style behavior → closer to O(n)

---

### B. Repeated computation

Before:

```python
for item in items:
    threshold = expensive_config_parse(config)
    process(item, threshold)
```

After:

```python
threshold = expensive_config_parse(config)

for item in items:
    process(item, threshold)
```

---

### C. Redundant I/O

Examples:

- repeated file reads
- repeated API calls
- repeated DB lookups
- repeated deserialization

Possible fixes:

- cache
- batch
- move invariant work outside loop

---

### D. Sequential independent work

Before:

```text
task A
task B
task C
```

Possible optimization:

```text
run independent tasks concurrently
```

Only apply when tests and benchmark confirm correctness.

---

### E. Inefficient data structures

Examples:

- list membership → set
- repeated linear search → dict
- unnecessary copying
- repeated sorting

---

### F. Repeated parsing/object creation

Examples:

- repeated regex compilation
- repeated JSON parsing
- repeated object construction
- repeated conversion of static data

---

## 8. Project architecture

Suggested structure:

```text
optimizer/
├── cli.py
├── scanner/
│   ├── project_scanner.py
│   ├── ast_parser.py
│   └── dependency_graph.py
├── profiler/
│   ├── runner.py
│   ├── profiler.py
│   └── hotspot_ranker.py
├── agent/
│   ├── context_builder.py
│   ├── optimizer_agent.py
│   └── candidate_generator.py
├── verifier/
│   ├── tests.py
│   ├── benchmark.py
│   ├── rollback.py
│   └── diff.py
├── models/
│   └── schemas.py
└── main.py
```

This structure can be simplified if time is tight.

---

## 9. Shared internal representation

The team should agree on one shared schema early so everyone can work independently.

Example hotspot object:

```json
{
  "function": "generate_feed",
  "qualified_name": "services.recommendations.generate_feed",
  "file": "services/recommendations.py",
  "line": 41,
  "calls": 10420,
  "self_time": 0.62,
  "cumulative_time": 1.82,
  "runtime_percent": 62.0,
  "dependencies": [
    "services.users.get_user",
    "database.find_user"
  ],
  "related_files": [
    "services/recommendations.py",
    "services/users.py",
    "database.py"
  ]
}
```

Possible candidate object:

```json
{
  "candidate_id": "candidate_a",
  "strategy": "batch user retrieval",
  "files_changed": [
    "services/recommendations.py",
    "services/users.py"
  ],
  "tests_passed": true,
  "benchmark_before_ms": 840,
  "benchmark_after_ms": 191,
  "speedup": 4.4,
  "accepted": true
}
```

---

## 10. Four-person team split

### Person 1 — Repository Intelligence

Own:

- scan repository
- find `.py` files
- ignore `.git`, `.venv`, `build`, `dist`, etc.
- parse AST
- extract:
  - functions
  - classes
  - imports
  - calls
- build basic dependency/call graph
- provide related code context around a hotspot

Primary output:

```json
{
  "function": "...",
  "file": "...",
  "dependencies": [...],
  "related_files": [...]
}
```

---

### Person 2 — Performance Engine

Own:

- execute benchmark command
- integrate `cProfile`
- parse profiler output
- rank hottest functions
- record baseline timings
- benchmark modified candidates
- re-profile after accepted changes

Primary output:

```json
{
  "function": "...",
  "calls": 10420,
  "cumulative_time": 1.82,
  "runtime_percent": 62
}
```

---

### Person 3 — Optimization Agent

Own:

- collect relevant function + dependency context
- build LLM prompt
- generate 2–3 optimization candidates
- require behavioral preservation
- produce structured candidate patches
- explain optimization strategy
- keep changes targeted to 1–3 files

Core prompt concept:

```text
You are optimizing a Python application for runtime performance.

The profiler identified this function as a measured hotspot.

Hotspot:
...

Profiler data:
...

Related functions:
...

Constraints:
- Preserve public behavior.
- Preserve function signatures unless absolutely required.
- Do not change unrelated code.
- Optimize runtime performance.
- Prefer algorithmic/data-structure improvements.
- Return a minimal patch.
```

---

### Person 4 — Safety, CLI, and Developer Experience

Own:

- CLI commands
- run tests
- detect failure
- backup files
- rollback failed candidate
- render git-style diff
- report before/after metrics
- polish terminal output
- coordinate final demo experience

Primary responsibility:

Make the project feel like a real developer tool rather than a script.

---

## 11. Integration contract

Each module should communicate with simple Python objects/dicts.

Suggested pipeline:

```python
project = scan_project(path)

profile = profile_project(
    project=project,
    command=benchmark_command
)

hotspot = rank_hotspots(profile)[0]

context = build_context(
    project=project,
    hotspot=hotspot
)

candidates = generate_candidates(context)

results = []

for candidate in candidates:
    apply_candidate(candidate)

    tests = run_tests(test_command)

    if not tests.passed:
        rollback()
        continue

    benchmark = run_benchmark(benchmark_command)

    results.append({
        "candidate": candidate,
        "tests": tests,
        "benchmark": benchmark,
    })

    rollback()

winner = choose_fastest_valid(results)

apply_candidate(winner)
```

---

## 12. Safety model

Every candidate change should follow:

```text
BACK UP ORIGINAL FILES
        ↓
APPLY CANDIDATE
        ↓
RUN TESTS
        ↓
TESTS FAIL?
   YES → ROLLBACK
   NO
        ↓
RUN BENCHMARK
        ↓
SLOWER?
   YES → ROLLBACK
   NO
        ↓
RECORD RESULT
```

Only accept candidates that:

- pass tests
- preserve expected output
- improve benchmark performance

---

## 13. Candidate selection

Generate 2–3 possible implementations.

Example:

```text
Original: 840 ms

Candidate A
Batch lookup
191 ms
PASS

Candidate B
Caching
303 ms
PASS

Candidate C
Concurrency
417 ms
FAIL TESTS

Winner:
Candidate A
```

This is a major product differentiator.

We are not trusting the model to know which solution is best.

**The benchmark decides.**

---

## 14. Benchmark strategy

For the MVP, the user supplies the workload.

Example:

```bash
optimizer run . \
  --benchmark "python benchmark.py"
```

Or:

```bash
optimizer run . \
  --benchmark "python scripts/load_test.py"
```

Do not spend the hackathon trying to infer every project's entry point automatically.

---

## 15. Test strategy

Preferred:

```bash
pytest -q
```

Allow custom command:

```bash
optimizer run . \
  --test "pytest tests/test_feed.py -q"
```

If the project has no tests, the MVP can:

- warn the user
- still benchmark
- require manual acceptance

Example:

```text
WARNING:
No test command provided.

Optimizer can measure performance,
but cannot automatically verify behavior.
```

---

## 16. Project scanner behavior

Ignore common directories:

```text
.git/
.venv/
venv/
__pycache__/
node_modules/
build/
dist/
.pytest_cache/
.mypy_cache/
```

Collect:

```text
*.py
```

AST extraction should identify:

- function definitions
- class methods
- imports
- calls
- file path
- line numbers

---

## 17. Hotspot ranking

For hackathon simplicity, rank primarily by:

```text
cumulative runtime
```

Potential score:

```text
score =
0.6 * normalized_cumulative_time
+ 0.2 * normalized_self_time
+ 0.2 * normalized_call_count
```

This does not need to be perfect.

The goal is to choose a meaningful measured bottleneck.

---

## 18. Cross-file reasoning

This is where the project becomes more than a single-file AI wrapper.

Example project:

```text
recommendations.py
    ↓
users.py
    ↓
database.py
```

Example:

```python
# users.py

def get_user(user_id):
    return database_lookup(user_id)
```

```python
# recommendations.py

for user_id in user_ids:
    user = get_user(user_id)
    generate_recommendations(user)
```

The individual files may look reasonable.

But repository-level profiling reveals:

```text
get_user()
10,420 calls

database_lookup()
10,420 calls
```

Optimizer can detect the interaction and propose:

- batching
- caching
- moving repeated work
- reducing unnecessary calls

This is the kind of demo we want.

---

## 19. Diff output

After selecting a candidate, show the developer exactly what changed.

Example:

```diff
- for user in users:
-     if user.id in [x.user_id for x in purchases]:
-         active.append(user)

+ purchased_user_ids = {x.user_id for x in purchases}
+
+ for user in users:
+     if user.id in purchased_user_ids:
+         active.append(user)
```

Then explain:

```text
Why this is faster:
The original code rebuilt and scanned a list during each loop iteration.

The new implementation creates a set once and uses average O(1) membership checks.
```

---

## 20. Final performance report

Example:

```text
Optimizer Report
────────────────────────────────

Repository
23 files
4,201 LOC
61 functions analyzed

Baseline
3.47 sec

Optimizations attempted
7

Accepted
3

Rejected
4
- 2 failed tests
- 2 produced slower benchmarks

Final runtime
0.91 sec

Overall improvement
74% faster

Speedup
3.8x

Tests
42/42 passing

Files changed
3
```

---

## 21. Demo repository

We should create our own small but realistic demo project.

Goal:

- multiple files
- 15–30 functions
- 3 deliberate performance bottlenecks
- tests included
- benchmark script included

Example domain:

```text
mini recommendation engine
```

Possible files:

```text
demo/
├── app.py
├── benchmark.py
├── services/
│   ├── recommendations.py
│   ├── users.py
│   └── search.py
├── data/
│   └── loader.py
└── tests/
    ├── test_recommendations.py
    └── test_search.py
```

Intentional bottlenecks:

1. repeated list membership
2. repeated expensive parsing
3. repeated lookup across files

The demo should be deterministic.

We should know in advance that the optimizations can create large wins.

---

## 22. Hackathon demo script

### Step 1 — Show slow project

```bash
python benchmark.py
```

Output:

```text
Runtime: 3.47 sec
```

---

### Step 2 — Run inspect

```bash
optimizer inspect .
```

Show:

```text
23 files analyzed
61 functions indexed

Top hotspot:
recommendations.generate_feed()

62% of runtime
10,420 repeated user lookups
```

---

### Step 3 — Run optimization

```bash
optimizer run . \
  --benchmark "python benchmark.py" \
  --test "pytest -q"
```

Show candidates being evaluated.

---

### Step 4 — Show winner

```text
Candidate A: 1.92 sec
Candidate B: 0.91 sec
Candidate C: rejected — tests failed

Selected Candidate B
```

---

### Step 5 — Show diff

Show actual multi-file changes.

---

### Step 6 — Show final result

```text
Before: 3.47 sec
After:  0.91 sec

3.8x faster
74% runtime reduction

42/42 tests passing
```

---

## 23. Judge pitch

### Short version

> Optimizer is an autonomous performance engineer for Python projects. Instead of asking an AI whether code looks inefficient, we profile the actual application, identify measured bottlenecks across the repository, generate multiple possible refactors, run the project's tests, benchmark every candidate, reject regressions, and automatically keep the fastest valid implementation.

### If asked: "Why not just use ChatGPT?"

> ChatGPT can suggest an optimization, but it does not automatically know whether that optimization actually improves the application. Optimizer profiles the running project, understands the execution path across files, tries multiple implementations, validates them with the project's tests, benchmarks each one, rejects failures, and re-profiles the application after each improvement. The model proposes changes, but the runtime decides which ones are actually better.

---

## 24. Product positioning

Possible descriptions:

### Option A

**Optimizer**
Autonomous performance engineering for your codebase.

### Option B

**Optimizer**
Profile. Refactor. Benchmark. Repeat.

### Option C

**Optimizer**
AI proposes. The runtime decides.

### Option D

**Optimizer**
Turn measured bottlenecks into verified performance improvements.

---

## 25. 12-hour execution plan

### Hour 0–1

Everyone:

- create repo
- choose schema/interfaces
- create demo project
- agree on CLI commands
- set up branches

Critical goal:

**Lock the integration contract immediately.**

---

### Hours 1–4

Parallel work:

**Person 1**
- project scanner
- AST parser
- function/import map

**Person 2**
- benchmark runner
- cProfile integration
- hotspot parser

**Person 3**
- LLM prompt
- candidate generation
- code patch generation

**Person 4**
- CLI
- test runner
- backup/rollback
- terminal UI

---

### Hour 4

Integration checkpoint.

Must have:

```text
repo
 ↓
scanner
 ↓
profiler
 ↓
hotspot object
```

Do not wait until the end to integrate.

---

### Hours 4–7

Connect:

```text
hotspot
 ↓
context builder
 ↓
LLM
 ↓
candidate patch
 ↓
apply patch
```

---

### Hours 7–9

Connect:

```text
candidate
 ↓
tests
 ↓
benchmark
 ↓
rollback / accept
```

Add best-of-3 selection.

---

### Hours 9–10

Add:

- git-style diff
- performance summary
- multi-pass mode if stable

---

### Hours 10–11

Polish:

- demo repository
- terminal output
- error handling
- deterministic benchmark
- clear before/after numbers

---

### Hour 11–12

Only:

- test demo repeatedly
- fix integration bugs
- prepare pitch
- record backup demo if rules allow
- do not add major features

---

## 26. MVP priority order

If time becomes tight, build in this order:

### P0 — Must work

1. CLI accepts project path
2. user provides benchmark command
3. profile project
4. identify hotspot
5. send relevant code to LLM
6. get one candidate optimization
7. apply candidate
8. run tests
9. benchmark
10. rollback if worse/failing
11. show before/after result

### P1 — Strong differentiators

12. whole-repo AST mapping
13. cross-file context
14. multiple candidate generation
15. select fastest candidate
16. git-style diff

### P2 — Nice to have

17. multi-pass optimization
18. richer hotspot scoring
19. beautiful terminal progress UI
20. automatic benchmark inference
21. optimization history

---

## 27. Definition of success

The hackathon MVP is successful if we can reliably demo:

```text
1. Point Optimizer at a multi-file Python project.
2. Profile the application.
3. Identify a real measured bottleneck.
4. Trace the bottleneck across related files.
5. Generate multiple candidate fixes.
6. Run tests automatically.
7. Benchmark each candidate.
8. Reject broken/slower candidates.
9. Apply the fastest valid implementation.
10. Show a clear measurable speedup.
```

We do **not** need to prove it can optimize every repository.

We need one convincing end-to-end workflow that demonstrates the product thesis.

---

## 28. Core principle

Everything we build should reinforce this idea:

> **AI proposes. The runtime decides.**

The LLM does not get to declare that code is better.

The profiler, test suite, and benchmark determine whether it is better.
