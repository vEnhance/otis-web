"""Server-side geometry for the locked-vs-shortfall charts on the scheme stats page.

Each chart plots two totals over time:

- Locked (blue): principal in bids whose growth timer is running.
- Shortfall (red): payouts promised beyond the principal paid in, i.e. profit
  already withdrawn plus the profit owed on every unlocked, unpaid bid.

The pool equals all unpaid principal minus profit already withdrawn, so paying
out every unlocked bid would overdraw it exactly when shortfall > locked.

The history chart runs from the first bid to now (or the collapse) and is
rebuilt from the timer log. The forecast chart runs from now to T later and
assumes no new bids, withdrawals, or upgrades; collapsed schemes don't get one.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone
from django.utils.dateformat import format as format_date

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
    anchor: str = "middle"


@dataclass
class Point:
    """Both totals from `when` until the next point."""

    when: datetime
    locked: int
    shortfall: Decimal
    x: float = 0
    y: float = 0
    y_shortfall: float = 0


@dataclass
class LockedChart:
    kind: str  # "history" or "forecast"
    start: datetime
    end: datetime
    points: list[Point]
    gestation_period: timedelta
    width: int = WIDTH
    height: int = HEIGHT
    left: int = MARGIN_LEFT
    right: int = WIDTH - MARGIN_RIGHT
    top: int = MARGIN_TOP
    bottom: int = HEIGHT - MARGIN_BOTTOM
    path: str = ""
    shortfall_path: str = ""
    x_ticks: list[Tick] = field(default_factory=list)
    y_ticks: list[Tick] = field(default_factory=list)

    @property
    def dom_id(self) -> str:
        return f"ponzi-chart-{self.kind}"

    @property
    def data_id(self) -> str:
        return f"{self.dom_id}-data"

    @property
    def plot_width(self) -> int:
        return self.right - self.left

    @property
    def plot_height(self) -> int:
        return self.bottom - self.top

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def axis_label(self) -> str:
        return "date" if self.kind == "history" else "time from now"

    def hover_data(self) -> dict[str, Any]:
        """What the crosshair script needs to read off both curves at any x."""
        unit, suffix = duration_unit(self.gestation_period)
        return {
            "kind": self.kind,
            "left": self.left,
            "right": self.right,
            "top": self.top,
            "bottom": self.bottom,
            "startMs": self.start.timestamp() * 1000,
            "endMs": self.end.timestamp() * 1000,
            "unitMs": unit.total_seconds() * 1000,
            "unit": suffix,
            "points": [
                [p.x, p.y, p.locked, p.y_shortfall, float(p.shortfall)]
                for p in self.points
            ],
        }

    def layout(self, y_max: int, y_step: int) -> None:
        """Turn the points into pixel positions, paths, and ticks."""
        span = max(self.end - self.start, timedelta(seconds=1))

        def px(when: datetime) -> float:
            return round(MARGIN_LEFT + PLOT_W * ((when - self.start) / span), 1)

        def py(value: float | Decimal) -> float:
            return round(self.bottom - PLOT_H * float(value) / y_max, 1)

        for p in self.points:
            p.x, p.y, p.y_shortfall = px(p.when), py(p.locked), py(p.shortfall)
        first, rest = self.points[0], self.points[1:]
        right = px(self.end)
        self.path = (
            f"M{first.x},{first.y}"
            + "".join(f"H{p.x}V{p.y}" for p in rest)
            + f"H{right}"
        )
        self.shortfall_path = (
            f"M{first.x},{first.y_shortfall}"
            + "".join(f"H{p.x}V{p.y_shortfall}" for p in rest)
            + f"H{right}"
        )
        tick_times = [
            self.start + span * i / NUM_X_TICKS for i in range(NUM_X_TICKS + 1)
        ]
        self.x_ticks = [Tick(px(t), self.tick_label(t, span)) for t in tick_times]
        self.x_ticks[-1].anchor = "end"  # keep the last label inside the chart
        self.y_ticks = [Tick(py(v), f"{v}♠") for v in range(0, y_max + 1, y_step)]

    def tick_label(self, when: datetime, span: timedelta) -> str:
        if self.kind == "forecast":
            offset = when - self.start
            if not offset:
                return "now"
            return "+" + format_duration(offset, self.gestation_period)
        fmt = "M j" if span >= timedelta(days=4) else "M j H:i"
        return format_date(timezone.localtime(when), fmt)


@dataclass
class LockedCharts:
    history: LockedChart | None
    forecast: LockedChart | None
    collapse_at: datetime | None


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


def sample(changes: Changes, start: datetime, end: datetime) -> list[Point]:
    """Both totals at `start`, then at every change in (start, end]."""
    locked, shortfall = 0, Decimal(0)
    points: list[Point] = []
    for when in sorted(changes):
        if when > end:
            break
        if when > start and not points:
            points.append(Point(start, locked, shortfall))
        d_locked, d_shortfall = changes[when]
        locked += d_locked
        shortfall += d_shortfall
        if when > start and (d_locked or d_shortfall):
            points.append(Point(when, locked, shortfall))
    if not points:
        points.append(Point(start, locked, shortfall))
    return points


def locked_charts(scheme: PonziScheme) -> LockedCharts:
    as_of = scheme.as_of
    T = scheme.gestation_period
    changes: Changes = {}
    for inv in scheme.investments.prefetch_related("timers"):
        add_bid_changes(inv, T, changes)
    if not changes:
        return LockedCharts(None, None, None)

    first_bid = min(changes)
    history = LockedChart(
        "history", first_bid, as_of, sample(changes, first_bid, as_of), T
    )
    forecast = None
    collapse_at = None
    if not scheme.has_collapsed:
        points = sample(changes, as_of, as_of + T)
        forecast = LockedChart("forecast", as_of, as_of + T, points, T)
        collapse_at = next((p.when for p in points if p.shortfall > p.locked), None)

    charts = [c for c in (history, forecast) if c is not None]
    peak = max(max(p.locked, math.ceil(p.shortfall)) for c in charts for p in c.points)
    y_step = nice_step(peak)
    y_max = max(y_step, math.ceil(peak / y_step) * y_step)
    for c in charts:
        c.layout(y_max, y_step)
    return LockedCharts(history, forecast, collapse_at)
