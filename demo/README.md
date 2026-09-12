# Demo: mini recommendation engine

A small deterministic project with three planted bottlenecks:

1. `app/parsing.py::parse_record` re-parses the same catalog lines for every user (repeated expensive parsing).
2. `app/users.py::get_user` scans the whole user table on every lookup, across files (repeated lookup).
3. `app/recommendations.py::filter_blocked` tests membership against a list, once per item (repeated list membership).

```bash
cd demo
python -m pytest -q                        # tests
python scripts/performance_scenario.py     # workload; prints Runtime and a checksum
```

From the repo root, let Optimizer at it:

```bash
python -m optimizer run demo \
  --workload "python scripts/performance_scenario.py" \
  --test "python -m pytest -q" \
  --hotspot parse_record --hotspot get_user --passes 2
```

`git checkout demo/` resets it afterwards.
