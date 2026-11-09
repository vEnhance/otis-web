from datetime import datetime, timedelta
from decimal import Decimal
from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.urls import reverse
from django.utils import timezone

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager

MAX_INVESTMENT = 10
INVESTMENT_COOLDOWN = timedelta(days=1)
TIER_RETURNS = {
    1: Decimal("0.067"),
    2: Decimal("0.14"),
    3: Decimal("0.34"),
}
MAX_TIER = max(TIER_RETURNS)
TIER_NAMES = {0: "—", 1: "I", 2: "II", 3: "III"}


class PonziScheme(models.Model):
    title = models.CharField(max_length=80)
    start_date = models.DateTimeField(help_text="When investments open")
    gestation_period = models.DurationField(
        help_text="How long a bid takes to reach its next tier"
    )
    collapsed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When somebody tried to withdraw more than the pool held",
    )
    collapsed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The user whose withdrawal broke the bank",
    )

    investments: "RelatedManager[PonziInvestment]"

    class Meta:
        ordering = ("-start_date",)

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("ponzi-scheme", args=(self.pk,))

    @property
    def has_started(self) -> bool:
        return timezone.now() >= self.start_date

    @property
    def has_collapsed(self) -> bool:
        return self.collapsed_at is not None

    @property
    def is_running(self) -> bool:
        return self.has_started and not self.has_collapsed

    @property
    def as_of(self) -> datetime:
        """The moment bid timers are measured against; growth freezes at collapse."""
        return self.collapsed_at or timezone.now()

    def _with_timer_start(self) -> "models.QuerySet[PonziInvestment]":
        """This scheme's bids, annotated with when their latest timer started."""
        latest = PonziTimer.objects.filter(investment=OuterRef("pk")).order_by("-tier")
        return self.investments.annotate(
            timer_started_at=Subquery(latest.values("started_at")[:1])
        )

    def locked_investments(self) -> "models.QuerySet[PonziInvestment]":
        """The bids for which PonziInvestment.is_growing holds."""
        cutoff = self.as_of - self.gestation_period
        return self._with_timer_start().filter(
            withdrawn_at__isnull=True, timer_started_at__gt=cutoff
        )

    def summary(self) -> dict[str, Any]:
        cutoff = self.as_of - self.gestation_period
        withdrawn = Q(withdrawn_at__isnull=False)
        locked = Q(withdrawn_at__isnull=True, timer_started_at__gt=cutoff)
        idle = Q(withdrawn_at__isnull=True, timer_started_at__lte=cutoff)
        stats = self._with_timer_start().aggregate(
            num_bids=Count("pk"),
            num_players=Count("user", distinct=True),
            total_bid=Sum("amount"),
            num_withdrawn=Count("pk", filter=withdrawn),
            total_paid=Sum("payout"),
            num_outstanding=Count("pk", filter=~withdrawn),
            total_outstanding=Sum("amount", filter=~withdrawn),
            num_idle=Count("pk", filter=idle),
            total_idle=Sum("amount", filter=idle),
            num_locked=Count("pk", filter=locked),
            total_locked=Sum("amount", filter=locked),
        )
        stats["pool"] = Decimal(stats["total_bid"] or 0) - (
            stats["total_paid"] or Decimal(0)
        )
        return stats

    def pool(self) -> Decimal:
        return self.summary()["pool"]


class PonziInvestment(models.Model):
    scheme_id: int
    timers: "RelatedManager[PonziTimer]"

    scheme = models.ForeignKey(
        PonziScheme, on_delete=models.CASCADE, related_name="investments"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_INVESTMENT)],
        help_text=f"Number of spades invested, at most {MAX_INVESTMENT}",
    )
    created_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    payout = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.amount}♠ by {self.user} in {self.scheme}"

    def refresh_from_db(self, *args: Any, **kwargs: Any) -> None:
        super().refresh_from_db(*args, **kwargs)
        vars(self).pop("current_timer", None)

    @cached_property
    def current_timer(self) -> "PonziTimer":
        """The latest timer; uses prefetched timers if there are any."""
        timers = list(self.timers.all())
        if not timers:  # only before the bid's first timer has been saved
            return PonziTimer(investment=self, tier=1, started_at=self.created_at)
        return max(timers, key=lambda t: t.tier)

    def start_timer(self, tier: int, started_at: datetime) -> "PonziTimer":
        timer = self.timers.create(tier=tier, started_at=started_at)
        vars(self)["current_timer"] = timer
        return timer

    @property
    def target_tier(self) -> int:
        """The tier this bid reaches once its current timer runs out."""
        return self.current_timer.tier

    @property
    def matures_at(self) -> datetime:
        return self.current_timer.started_at + self.scheme.gestation_period

    @property
    def hours_past_maturity(self) -> float:
        return (self.scheme.as_of - self.matures_at).total_seconds() / 3600

    @property
    def hours_until_maturity(self) -> float:
        return -self.hours_past_maturity

    @property
    def is_growing(self) -> bool:
        return self.withdrawn_at is None and self.hours_past_maturity < 0

    @property
    def tier(self) -> int:
        return self.target_tier - 1 if self.is_growing else self.target_tier

    @property
    def tier_name(self) -> str:
        return TIER_NAMES[self.tier]

    @property
    def can_withdraw(self) -> bool:
        return self.withdrawn_at is None and not self.is_growing

    @property
    def can_upgrade(self) -> bool:
        return self.can_withdraw and self.target_tier < MAX_TIER

    def value_at_tier(self, tier: int) -> Decimal:
        return (self.amount * (1 + TIER_RETURNS[tier])).quantize(Decimal("0.01"))

    @property
    def current_value(self) -> Decimal:
        return self.value_at_tier(self.tier) if self.tier else Decimal(self.amount)

    @property
    def spades_delta(self) -> Decimal:
        return (self.payout or Decimal(0)) - self.amount


class PonziTimer(models.Model):
    """One growth timer on a bid: the bid is locked from `started_at` until a
    gestation period later, after which it is worth `tier`."""

    investment = models.ForeignKey(
        PonziInvestment, on_delete=models.CASCADE, related_name="timers"
    )
    tier = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TIER)],
        help_text="The tier the bid reaches when this timer runs out",
    )
    started_at = models.DateTimeField()
    inferred = models.BooleanField(
        default=False,
        help_text="Backfilled guess for an upgrade made before timers were logged",
    )

    class Meta:
        ordering = ("investment", "tier")
        constraints = (
            models.UniqueConstraint(
                fields=("investment", "tier"), name="unique_timer_per_tier"
            ),
        )

    def __str__(self) -> str:
        return f"Tier {TIER_NAMES[self.tier]} timer for {self.investment}"
