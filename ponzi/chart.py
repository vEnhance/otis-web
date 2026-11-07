"""Server-side geometry for the locked-spades chart on the scheme stats page.

For each x in [0, T], the curve shows the total spades in still-growing bids
whose current timer has been running for at most x. So the curve ends at the
total locked amount, and how fast it rises shows how soon those spades unlock.
"""

import math
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import groupby
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
    """A jump in the curve: `amount` spades whose growth is exactly `growth`."""

    growth: timedelta
    amount: int
    cumulative: int
    num_bids: int
    x: float = 0
    y: float = 0


@dataclass
class LockedChart:
    gestation_period: timedelta
    steps: list[Step]
    total: int
    y_max: int
    width: int = WIDTH
    height: int = HEIGHT
    left: int = MARGIN_LEFT
    right: int = WIDTH - MARGIN_RIGHT
    top: int = MARGIN_TOP
    bottom: int = HEIGHT - MARGIN_BOTTOM
    path: str = ""
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

    def hover_data(self) -> dict[str, Any]:
        """What the crosshair script needs to read off f(x) at any cursor position."""
        unit, suffix = duration_unit(self.gestation_period)
        return {
            "left": self.left,
            "right": self.right,
            "top": self.top,
            "bottom": self.bottom,
            "span": self.gestation_period / unit,
            "unit": suffix,
            "steps": [[s.x, s.y, s.cumulative] for s in self.steps],
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
    growths = sorted(
        (as_of - (inv.upgraded_at or inv.created_at), inv.amount)
        for inv in scheme.locked_investments()
    )

    steps: list[Step] = []
    cumulative = 0
    for growth, group in groupby(growths, key=lambda pair: pair[0]):
        amounts = [amount for _, amount in group]
        cumulative += sum(amounts)
        steps.append(Step(growth, sum(amounts), cumulative, len(amounts)))

    step = nice_step(cumulative)
    y_max = max(step, math.ceil(cumulative / step) * step)
    chart = LockedChart(T, steps, cumulative, y_max)

    def px(growth: timedelta) -> float:
        return round(MARGIN_LEFT + PLOT_W * min(growth / T, 1), 1)

    def py(value: int) -> float:
        return round(chart.bottom - PLOT_H * value / y_max, 1)

    d = [f"M{px(timedelta(0))},{py(0)}"]
    for s in steps:
        s.x, s.y = px(s.growth), py(s.cumulative)
        d.append(f"H{s.x}V{s.y}")
    d.append(f"H{px(T)}")
    chart.path = "".join(d)

    chart.x_ticks = [
        Tick(px(T * i / NUM_X_TICKS), format_duration(T * i / NUM_X_TICKS, T))
        for i in range(NUM_X_TICKS + 1)
    ]
    chart.y_ticks = [Tick(py(v), f"{v}♠") for v in range(0, y_max + 1, step)]
    return chart
