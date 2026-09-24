from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

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

    investments: "models.Manager[PonziInvestment]"

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

    def summary(self) -> dict[str, Any]:
        withdrawn = Q(withdrawn_at__isnull=False)
        stats = self.investments.aggregate(
            num_bids=Count("pk"),
            num_players=Count("user", distinct=True),
            total_bid=Sum("amount"),
            num_withdrawn=Count("pk", filter=withdrawn),
            total_paid=Sum("payout"),
            num_outstanding=Count("pk", filter=~withdrawn),
            total_outstanding=Sum("amount", filter=~withdrawn),
        )
        stats["pool"] = Decimal(stats["total_bid"] or 0) - (
            stats["total_paid"] or Decimal(0)
        )
        return stats

    def pool(self) -> Decimal:
        return self.summary()["pool"]


class PonziInvestment(models.Model):
    scheme_id: int

    scheme = models.ForeignKey(
        PonziScheme, on_delete=models.CASCADE, related_name="investments"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_INVESTMENT)],
        help_text=f"Number of spades invested, at most {MAX_INVESTMENT}",
    )
    target_tier = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TIER)],
        help_text="The tier this investment reaches once its current timer runs out",
    )
    created_at = models.DateTimeField(default=timezone.now)
    upgraded_at = models.DateTimeField(
        null=True, blank=True, help_text="When the most recent upgrade timer started"
    )
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    payout = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.amount}♠ by {self.user} in {self.scheme}"

    @property
    def matures_at(self) -> datetime:
        return (self.upgraded_at or self.created_at) + self.scheme.gestation_period

    @property
    def is_growing(self) -> bool:
        return self.withdrawn_at is None and timezone.now() < self.matures_at

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
