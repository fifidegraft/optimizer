"""Catalog line parsing. Lines look like:

    item:42|tags:books,fiction|score:7.5|checksum:...

Parsing is pure and deterministic, and the catalog is re-parsed for every
user because nobody cached it.
"""

import re

_LINE = re.compile(r"item:(?P<item>\d+)\|tags:(?P<tags>[^|]*)\|score:(?P<score>[0-9.]+)")


def _checksum(text):
    total = 0
    for _ in range(10):
        for ch in text:
            total = (total * 31 + ord(ch)) % 1000003
    return total


def parse_tags(field):
    return tuple(tag.strip() for tag in field.split(",") if tag.strip())


def parse_score(field):
    return round(float(field), 2)


def parse_record(raw):
    """Intentional bottleneck: expensive, pure, and called again and again on the same lines."""
    match = _LINE.match(raw)
    if match is None:
        raise ValueError(f"bad catalog line: {raw!r}")
    item_id = int(match.group("item"))
    tags = parse_tags(match.group("tags"))
    score = parse_score(match.group("score"))
    return (item_id, tags, score, _checksum(raw))
