"""Server-side geometry for the locked-vs-shortfall chart on the scheme stats page.

The chart spans T either side of "now" (or of the collapse, for a collapsed
scheme). At each moment it shows two totals:

- Locked (blue): principal in bids whose growth timer is running.
- Shortfall (red): payouts promised beyond the principal paid in, i.e. profit
  already withdrawn plus the profit owed on every unlocked, unpaid bid.

The pool equals all unpaid principal minus profit already withdrawn, so paying
out every unlocked bid would overdraw it exactly when shortfall > locked.
The past half is reconstructed from the timer log; the future half assumes no
new bids, withdrawals, or upgrades.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from .models import PonziInvestment, PonziScheme

WIDTH = 640
HEIGHT = 280
MARGIN_LEFT = 60
MARGIN_RIGHT = 16
MARGIN_TOP = 16
MARGIN_BOTTOM = 50
PLOT_W = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
PLOT_H = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
NUM_X_TICKS = 4


@dataclass
class Tick:
    pos: float
    label: str


@dataclass
class Point:
    """Both totals from `offset` (relative to now) until the next point."""

    offset: timedelta
    locked: int
    shortfall: Decimal
    x: float = 0
    y: float = 0
    y_shortfall: float = 0


@dataclass
class LockedChart:
    gestation_period: timedelta
    collapsed: bool
    points: list[Point]
    now: Point
    collapse_in: timedelta | None
    y_max: int
    width: int = WIDTH
    height: int = HEIGHT
    left: int = MARGIN_LEFT
    right: int = WIDTH - MARGIN_RIGHT
    top: int = MARGIN_TOP
    bottom: int = HEIGHT - MARGIN_BOTTOM
    now_x: float = 0
    path: str = ""
    shortfall_path: str = ""
    x_ticks: list[Tick] = field(default_factory=list)
    y_ticks: list[Tick] = field(default_factory=list)

    @property
    def plot_width(self) -> int:
        return self.right - self.left

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def plot_height(self) -> int:
        return self.bottom - self.top

    @property
    def axis_label(self) -> str:
        return "time relative to collapse" if self.collapsed else "time relative to now"

    @property
    def collapse_label(self) -> str | None:
        if self.collapse_in is None:
            return None
        return format_duration(self.collapse_in, self.gestation_period)

    def hover_data(self) -> dict[str, Any]:
        """What the crosshair script needs to read off both curves at any x."""
        unit, suffix = duration_unit(self.gestation_period)
        return {
            "left": self.left,
            "right": self.right,
            "top": self.top,
            "bottom": self.bottom,
            "span": self.gestation_period / unit,
            "unit": suffix,
            "collapsed": self.collapsed,
            "points": [
                [p.x, p.y, p.locked, p.y_shortfall, float(p.shortfall)]
                for p in self.points
            ],
        }


def duration_unit(gestation_period: timedelta) -> tuple[timedelta, str]:
    """Days for long schemes, hours for short ones."""
    if gestation_period >= timedelta(days=2):
        return timedelta(days=1), "d"
    return timedelta(hours=1), "h"


def format_duration(d: timedelta, gestation_period: timedelta) -> str:
    unit, suffix = duration_unit(gestation_period)
    return f"{d / unit:.3g}{suffix}"


def nice_step(total: int, num_ticks: int = 4) -> int:
    """The smallest 1/2/5 * 10^k integer step that covers `total` in `num_ticks`."""
    raw = max(total / num_ticks, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 5, 10):
        if mult * magnitude >= raw:
            return int(mult * magnitude)
    raise AssertionError("unreachable")


Changes = dict[datetime, list[Any]]  # time -> [change in locked, change in shortfall]


def add_bid_changes(inv: PonziInvestment, T: timedelta, changes: Changes) -> None:
    """Record when this bid starts and stops counting toward each curve."""

    def add(when: datetime, locked: int, shortfall: Decimal) -> None:
        delta = changes.setdefault(when, [0, Decimal(0)])
        delta[0] += locked
        delta[1] += shortfall

    timers = [(t.tier, t.started_at) for t in inv.timers.all()]
    if not timers:  # can't happen once the backfill has run, but be safe
        timers = [(1, inv.created_at)]
    for i, (tier, started_at) in enumerate(timers):
        # the bid sits idle at `tier` from maturity until the next timer or payout
        idle_until = timers[i + 1][1] if i + 1 < len(timers) else inv.withdrawn_at
        matures_at = started_at + T
        if idle_until is not None:
            matures_at = min(matures_at, idle_until)
        add(started_at, inv.amount, Decimal(0))
        add(matures_at, -inv.amount, Decimal(0))
        profit = inv.value_at_tier(tier) - inv.amount
        add(matures_at, 0, profit)
        if idle_until is not None:
            add(idle_until, 0, -profit)
    if inv.withdrawn_at is not None:
        add(inv.withdrawn_at, 0, (inv.payout or Decimal(0)) - inv.amount)


def locked_chart(scheme: PonziScheme) -> LockedChart:
    as_of = scheme.as_of
    T = scheme.gestation_period
    start, end = as_of - T, as_of + T

    changes: Changes = {}
    for inv in scheme.investments.prefetch_related("timers"):
        add_bid_changes(inv, T, changes)

    locked, shortfall = 0, Decimal(0)
    points: list[Point] = []
    now: Point | None = None
    for when in sorted(changes):
        if when > start and not points:
            points.append(Point(-T, locked, shortfall))
        if when > as_of and now is None:
            now = Point(timedelta(0), locked, shortfall)
        if when > end:
            break
        d_locked, d_shortfall = changes[when]
        locked += d_locked
        shortfall += d_shortfall
        if when > start and (d_locked or d_shortfall):
            points.append(Point(when - as_of, locked, shortfall))
    if not points:
        points.append(Point(-T, locked, shortfall))
    if now is None:
        now = Point(timedelta(0), locked, shortfall)

    collapse_in = None
    for p in [now, *(p for p in points if p.offset > timedelta(0))]:
        if p.shortfall > p.locked:
            collapse_in = p.offset
            break

    peak = max(max(p.locked, math.ceil(p.shortfall)) for p in points)
    step = nice_step(peak)
    y_max = max(step, math.ceil(peak / step) * step)
    chart = LockedChart(
        gestation_period=T,
        collapsed=scheme.has_collapsed,
        points=points,
        now=now,
        collapse_in=collapse_in,
        y_max=y_max,
    )

    def px(offset: timedelta) -> float:
        return round(MARGIN_LEFT + PLOT_W * (offset + T) / (2 * T), 1)

    def py(value: float | Decimal) -> float:
        return round(chart.bottom - PLOT_H * float(value) / y_max, 1)

    for p in points:
        p.x, p.y, p.y_shortfall = px(p.offset), py(p.locked), py(p.shortfall)
    first, rest = points[0], points[1:]
    chart.path = f"M{first.x},{first.y}" + "".join(f"H{p.x}V{p.y}" for p in rest)
    chart.shortfall_path = f"M{first.x},{first.y_shortfall}" + "".join(
        f"H{p.x}V{p.y_shortfall}" for p in rest
    )
    chart.path += f"H{px(T)}"
    chart.shortfall_path += f"H{px(T)}"
    chart.now_x = px(timedelta(0))

    def tick_label(offset: timedelta) -> str:
        if not offset:
            return "collapse" if chart.collapsed else "now"
        sign = "+" if offset > timedelta(0) else "−"
        return sign + format_duration(abs(offset), T)

    tick_offsets = [
        T * (2 * i - NUM_X_TICKS) / NUM_X_TICKS for i in range(NUM_X_TICKS + 1)
    ]
    chart.x_ticks = [Tick(px(o), tick_label(o)) for o in tick_offsets]
    chart.y_ticks = [Tick(py(v), f"{v}♠") for v in range(0, y_max + 1, step)]
    return chart
