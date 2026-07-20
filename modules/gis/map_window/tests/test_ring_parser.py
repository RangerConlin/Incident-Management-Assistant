from modules.gis.map_window.tools.draw_tools import parse_ring_distances


def test_parses_and_sorts_valid_distances():
    assert parse_ring_distances("500, 100, 250") == [100.0, 250.0, 500.0]


def test_dedupes_equal_values():
    assert parse_ring_distances("100, 100, 100.0") == [100.0]


def test_rejects_invalid_and_nonpositive_tokens():
    assert parse_ring_distances("1, 1, -2, abc, 3") == [1.0, 3.0]


def test_rejects_zero():
    assert parse_ring_distances("0, 5") == [5.0]


def test_empty_input():
    assert parse_ring_distances("") == []
    assert parse_ring_distances(None) == []


def test_whitespace_and_blank_tokens_ignored():
    assert parse_ring_distances(" 10 ,, 20 ,  ") == [10.0, 20.0]
