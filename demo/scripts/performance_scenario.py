"""Workload: build feeds for a stream of users. Deterministic; prints runtime and a checksum.

    python scripts/performance_scenario.py        # from demo/
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog import raw_catalog_lines
from app.recommendations import generate_feed

USERS = 2000  # ids repeat every 150, so caching pays off
RAW_LINES = raw_catalog_lines(40)
BLOCKED = list(range(0, 40, 4))


def main():
    user_ids = [(i % 150) * 33 for i in range(USERS)]  # 150 distinct ids spread over the table
    start = time.perf_counter()
    feed = generate_feed(user_ids, RAW_LINES, BLOCKED)
    elapsed_ms = (time.perf_counter() - start) * 1000
    checksum = sum(uid * 31 + sum(items) for uid, items in feed) % 1000003
    print(f"feeds: {len(feed)}  checksum: {checksum}")
    print(f"Runtime: {elapsed_ms:.0f} ms")


if __name__ == "__main__":
    main()
