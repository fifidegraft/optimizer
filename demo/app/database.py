"""Toy in-memory 'database' so the demo has something to be slow about.

Rows live in a list and lookups scan it, the way a naive ORM-free script
would hit a table without an index.
"""

_ROWS = [
    {"id": i, "name": f"user_{i}", "tier": ("free", "plus", "pro")[i % 3], "region": i % 7}
    for i in range(5000)
]


def _row_matches(row, user_id):
    return row["id"] == user_id


def find_user(user_id):
    # Pretend this is an expensive round trip: a full scan per lookup.
    for row in _ROWS:
        if _row_matches(row, user_id):
            return row
    return None


def all_users():
    return list(_ROWS)


def items_for_user(user_id):
    """Item ids this user already interacted with; deterministic per user."""
    return [(user_id * 7 + k) % 300 for k in range(5)]
