from app.catalog import item_by_id, load_catalog, raw_catalog_lines
from app.parsing import parse_record, parse_tags
from app.recommendations import filter_blocked, generate_feed, rank_items
from app.users import display_name, get_user, get_users

LINES = raw_catalog_lines(12)


def test_parse_record_fields():
    item_id, tags, score, checksum = parse_record("item:42|tags:books, fiction|score:7.5")
    assert item_id == 42
    assert tags == ("books", "fiction")
    assert score == 7.5
    assert isinstance(checksum, int)


def test_parse_record_is_deterministic():
    assert parse_record(LINES[3]) == parse_record(LINES[3])
    assert parse_record(LINES[3]) != parse_record(LINES[4])


def test_parse_tags_and_bad_line():
    assert parse_tags("a,,b ,") == ("a", "b")
    try:
        parse_record("nonsense")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_get_user_found_and_missing():
    assert get_user(7) == {"id": 7, "name": "user_7", "tier": "plus", "region": 0}
    assert get_user(999999) is None
    assert display_name(get_user(3)) == "user_3 (free)"


def test_get_users_skips_unknown():
    assert [u["id"] for u in get_users([1, 424242, 2])] == [1, 2]


def test_filter_blocked_uses_a_list():
    items = load_catalog(LINES)
    kept = filter_blocked(items, [0, 1, 2])
    assert [item[0] for item in kept] == list(range(3, 12))
    assert item_by_id(items, 5)[0] == 5 and item_by_id(items, 99) is None


def test_rank_items_is_deterministic_and_sorted():
    user = get_user(5)
    ranked = rank_items(user, LINES)
    assert ranked == rank_items(user, LINES)
    assert len(ranked) == len(LINES)
    assert [item[0] for item in ranked] != list(range(12))  # actually reordered


def test_generate_feed_golden():
    feed = generate_feed([1, 424242, 2, 1], LINES, [3], n=2)
    assert [uid for uid, _ in feed] == [1, 2, 1]
    assert feed[0] == feed[2]
    assert all(3 not in items for _, items in feed)
    assert all(len(items) == 2 for _, items in feed)
