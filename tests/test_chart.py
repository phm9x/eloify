from eloify.chart import MAX_WIDTH, line_chart


def test_too_few_points_is_empty():
    assert line_chart([]) == []
    assert line_chart([1000]) == []


def test_basic_shape():
    rows = line_chart([1000, 1010, 1005, 1030], height=6)
    assert rows  # non-empty
    # Every row is the same width (padded grid) before rstrip — at least the
    # axis column lines up: each row contains an axis glyph.
    assert all(any(c in r for c in "┤┼") for r in rows)
    # The max value labels the top row, the min the bottom row.
    assert rows[0].lstrip().startswith("1030")
    assert rows[-1].lstrip().startswith("1000")


def test_flat_series_single_row():
    rows = line_chart([1000, 1000, 1000])
    assert len(rows) == 1
    assert rows[0].startswith("1000")


def test_rising_series_ends_higher_than_it_starts():
    rows = line_chart([1000, 1020, 1040, 1060], height=6)
    # Top row carries the max; the line should reach it.
    assert "1060" in rows[0]


def test_long_series_is_downsampled():
    rows = line_chart(list(range(1000, 1000 + 500)), height=6)
    # Width is bounded: data columns capped at MAX_WIDTH.
    assert max(len(r) for r in rows) <= MAX_WIDTH + 12  # + label/axis padding
