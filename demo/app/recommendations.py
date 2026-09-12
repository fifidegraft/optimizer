from .database import items_for_user
from .parsing import parse_record
from .users import get_user


def filter_blocked(items, blocked_ids):
    """Intentional bottleneck: membership test against a list, once per item."""
    kept = []
    for item in items:
        if item[0] not in blocked_ids:
            kept.append(item)
    return kept


def score_item(user, item):
    item_id, tags, score, _checksum = item
    bonus = 2.0 if user["tier"] == "pro" else 1.0
    affinity = 1.5 if item_id in items_for_user(user["id"]) else 1.0
    return score * bonus * affinity + len(tags) * 0.1


def rank_items(user, raw_lines):
    """Intentional bottleneck: re-parses the whole catalog for every user."""
    scored = []
    for line in raw_lines:
        item = parse_record(line)
        scored.append((score_item(user, item), item))
    scored.sort(key=lambda pair: (-pair[0], pair[1][0]))
    return [item for _score, item in scored]


def top_n(items, n):
    return items[:n]


def generate_feed(user_ids, raw_lines, blocked_ids, n=3):
    """Intentional bottleneck: looks up each user one at a time, across files."""
    feed = []
    for user_id in user_ids:
        user = get_user(user_id)
        if user is None:
            continue
        ranked = rank_items(user, raw_lines)
        allowed = filter_blocked(ranked, blocked_ids)
        feed.append((user["id"], [item[0] for item in top_n(allowed, n)]))
    return feed
