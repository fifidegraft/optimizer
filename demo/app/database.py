"""Toy in-memory 'database' so the demo has something to be slow about."""

_USERS = {i: {"id": i, "name": f"user_{i}"} for i in range(2000)}


def find_user(user_id):
    # Pretend this is an expensive round trip.
    return _USERS.get(user_id)
