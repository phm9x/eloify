"""A tiny dependency-free terminal line chart (asciichart-style).

`line_chart` turns a numeric series into rows of text with a labelled y-axis,
drawn with box/diagonal characters:

    1042 ┤            ╭╮
    1011 ┤        ╭───╯╰╮
     980 ┼────────╯     ╰
         g1            g14

It's intentionally small — just enough to sketch a rating trend in the
`elo history` output. Long series are evenly downsampled to keep the width
sane in a terminal.
"""

from __future__ import annotations

MAX_WIDTH = 60  # data columns; longer series are downsampled to this


def _downsample(series: list[float], width: int) -> list[float]:
    """Evenly pick `width` points (always keeping the first and last)."""
    n = len(series)
    if n <= width:
        return series
    step = (n - 1) / (width - 1)
    return [series[round(i * step)] for i in range(width)]


def line_chart(series: list[float], height: int = 8) -> list[str]:
    """Render `series` as a list of text rows. Empty if there's nothing to plot."""
    series = _downsample([float(v) for v in series], MAX_WIDTH)
    if len(series) < 2:
        return []

    lo, hi = min(series), max(series)
    interval = hi - lo

    # Flat line: one labelled row, no vertical resolution to show.
    if interval == 0:
        label = f"{lo:.0f}"
        return [f"{label} ┼" + "─" * len(series)]

    ratio = height / interval
    min2 = round(lo * ratio)
    max2 = round(hi * ratio)
    rows = max(max2 - min2, 1)

    labels = [f"{hi - y * interval / rows:.0f}" for y in range(rows + 1)]
    label_w = max(len(s) for s in labels)
    axis_col = label_w + 1  # one space between the label and the axis
    offset = axis_col + 1
    grid = [[" "] * (offset + len(series)) for _ in range(rows + 1)]

    for y in range(rows + 1):
        for i, ch in enumerate(labels[y].rjust(label_w)):
            grid[y][i] = ch
        grid[y][axis_col] = "┤"

    def row_of(value: float) -> int:
        return rows - (round(value * ratio) - min2)

    grid[row_of(series[0])][axis_col] = "┼"
    for x in range(len(series) - 1):
        y0 = row_of(series[x])
        y1 = row_of(series[x + 1])
        col = x + offset
        if y0 == y1:
            grid[y0][col] = "─"
            continue
        # y decreases upward, so y1 < y0 means the value rose.
        grid[y1][col] = "╰" if y1 > y0 else "╭"
        grid[y0][col] = "╮" if y1 > y0 else "╯"
        for y in range(min(y0, y1) + 1, max(y0, y1)):
            grid[y][col] = "│"

    return ["".join(r).rstrip() for r in grid]
