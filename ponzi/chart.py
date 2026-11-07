"""Server-side geometry for the locked-spades chart on the scheme stats page.

Both curves look x into the future (x in [0, T]) assuming no new bids,
withdrawals, or upgrades. For a collapsed scheme, "now" is the collapse.

- Locked (blue): spades in still-growing bids with more than x left on their
  timer. These are guaranteed to still be in the pool x from now.
- Shortfall (red): payouts promised beyond the principal that was paid in,
  i.e. profit already withdrawn plus profit owed on every bid unlocked by x.

The pool equals all unpaid principal minus profit already withdrawn, so paying
out every unlocked bid would overdraw it exactly when shortfall > locked.
That first crossing is the earliest the scheme could collapse.
"""

import math
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from .models import PonziScheme

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
class Step:
    """Bids unlocking once `time_left` has passed: `amount` spades leave the
    locked curve and `profit` is added to the shortfall curve."""

    time_left: timedelta
    amount: int
    profit: Decimal
    remaining: int
    shortfall: Decimal
    num_bids: int
    x: float = 0
    y: float = 0
    y_shortfall: float = 0


@dataclass
class LockedChart:
    gestation_period: timedelta
    collapsed: bool
    steps: list[Step]
    total: int
    initial_shortfall: Decimal
    collapse_in: timedelta | None
    y_max: int
    width: int = WIDTH
    height: int = HEIGHT
    left: int = MARGIN_LEFT
    right: int = WIDTH - MARGIN_RIGHT
    top: int = MARGIN_TOP
    bottom: int = HEIGHT - MARGIN_BOTTOM
    path: str = ""
    shortfall_path: str = ""
    total_y: float = 0
    initial_shortfall_y: float = 0
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
        return "time after collapse" if self.collapsed else "time from now"

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
            "span": self.gestation_period / unit,
            "unit": suffix,
            "prefix": "+" if self.collapsed else "in ",
            "start": [
                self.total_y,
                self.total,
                self.initial_shortfall_y,
                float(self.initial_shortfall),
            ],
            "steps": [
                [s.x, s.y, s.remaining, s.y_shortfall, float(s.shortfall)]
                for s in self.steps
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


def locked_chart(scheme: PonziScheme) -> LockedChart:
    as_of = scheme.as_of
    T = scheme.gestation_period

    shortfall = Decimal(0)
    unlocks: dict[timedelta, list[tuple[int, Decimal]]] = {}
    for inv in scheme.investments.select_related("scheme"):
        if inv.withdrawn_at is not None:
            shortfall += (inv.payout or Decimal(0)) - inv.amount
        elif inv.matures_at > as_of:
            profit = inv.value_at_tier(inv.target_tier) - inv.amount
            unlocks.setdefault(inv.matures_at - as_of, []).append((inv.amount, profit))
        else:
            shortfall += inv.current_value - inv.amount
    initial_shortfall = shortfall
    total = sum(amount for bids in unlocks.values() for amount, _ in bids)

    steps: list[Step] = []
    remaining = total
    collapse_in = timedelta(0) if shortfall > remaining else None
    for time_left in sorted(unlocks):
        bids = unlocks[time_left]
        amount = sum(a for a, _ in bids)
        profit = sum((p for _, p in bids), Decimal(0))
        remaining -= amount
        shortfall += profit
        steps.append(Step(time_left, amount, profit, remaining, shortfall, len(bids)))
        if collapse_in is None and shortfall > remaining:
            collapse_in = time_left

    peak = max(total, math.ceil(shortfall))
    step = nice_step(peak)
    y_max = max(step, math.ceil(peak / step) * step)
    chart = LockedChart(
        T, scheme.has_collapsed, steps, total, initial_shortfall, collapse_in, y_max
    )

    def px(d: timedelta) -> float:
        return round(MARGIN_LEFT + PLOT_W * min(d / T, 1), 1)

    def py(value: float | Decimal) -> float:
        return round(chart.bottom - PLOT_H * float(value) / y_max, 1)

    chart.total_y = py(total)
    chart.initial_shortfall_y = py(initial_shortfall)
    locked_d = [f"M{px(timedelta(0))},{chart.total_y}"]
    shortfall_d = [f"M{px(timedelta(0))},{chart.initial_shortfall_y}"]
    for s in steps:
        s.x, s.y, s.y_shortfall = px(s.time_left), py(s.remaining), py(s.shortfall)
        locked_d.append(f"H{s.x}V{s.y}")
        shortfall_d.append(f"H{s.x}V{s.y_shortfall}")
    locked_d.append(f"H{px(T)}")
    shortfall_d.append(f"H{px(T)}")
    chart.path = "".join(locked_d)
    chart.shortfall_path = "".join(shortfall_d)

    chart.x_ticks = [
        Tick(px(T * i / NUM_X_TICKS), format_duration(T * i / NUM_X_TICKS, T))
        for i in range(NUM_X_TICKS + 1)
    ]
    chart.y_ticks = [Tick(py(v), f"{v}♠") for v in range(0, y_max + 1, step)]
    return chart
