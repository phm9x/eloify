"""Tiny inline-SVG sparkline for rating trends — the browser analog of
`chart.line_chart`. Returns a self-contained `<svg>` string (no external deps,
styled via CSS classes) or "" when there aren't enough points to draw."""

from __future__ import annotations


def sparkline_svg(
    series: list[float],
    width: int = 520,
    height: int = 150,
    pad: int = 22,
) -> str:
    """Render a numeric series as an inline SVG polyline with min/max labels.

    Returns "" for fewer than two points (matching `line_chart`, which a caller
    can fall back on / hide).
    """
    if not series or len(series) < 2:
        return ""

    lo, hi = min(series), max(series)
    span = (hi - lo) or 1.0
    n = len(series)
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad

    def x(i: int) -> float:
        return pad + inner_w * i / (n - 1)

    def y(v: float) -> float:
        return pad + inner_h * (1 - (v - lo) / span)

    pts = [(x(i), y(v)) for i, v in enumerate(series)]
    line = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    # An area under the line for a little fill.
    area = (
        f"{pts[0][0]:.1f},{height - pad:.1f} "
        + line
        + f" {pts[-1][0]:.1f},{height - pad:.1f}"
    )
    lx, ly = pts[-1]

    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" role="img" '
        f'aria-label="rating trend from {series[0]:.0f} to {series[-1]:.0f}">'
        f'<polyline class="spark-area" points="{area}" />'
        f'<polyline class="spark-line" points="{line}" />'
        f'<circle class="spark-dot" cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" />'
        f'<text class="spark-label" x="2" y="{pad - 6:.0f}">{hi:.0f}</text>'
        f'<text class="spark-label" x="2" y="{height - pad + 12:.0f}">{lo:.0f}</text>'
        f"</svg>"
    )
