from .parsing import parse_record

_TAGS = ("books", "fiction", "music", "games", "tools", "travel", "food")


def raw_catalog_lines(count=120):
    """Deterministic catalog: the same lines every run."""
    lines = []
    for i in range(count):
        tags = ",".join(_TAGS[(i + k) % len(_TAGS)] for k in range(1 + i % 3))
        lines.append(f"item:{i}|tags:{tags}|score:{(i * 37) % 100 / 10:.1f}")
    return lines


def load_catalog(raw_lines):
    return [parse_record(line) for line in raw_lines]


def item_by_id(items, item_id):
    for item in items:
        if item[0] == item_id:
            return item
    return None
