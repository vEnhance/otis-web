import datetime
from typing import Any

from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker

from core.factories import UserFactory

from .models import PonziInvestment, PonziScheme, PonziTimer


class PonziSchemeFactory(DjangoModelFactory):
    class Meta:
        model = PonziScheme

    title = Faker("bs")
    start_date = Faker("past_datetime", tzinfo=datetime.UTC)
    gestation_period = datetime.timedelta(weeks=2)


class PonziInvestmentFactory(DjangoModelFactory):
    """Accepts `target_tier` and `upgraded_at` and turns them into timers,
    guessing any intermediate upgrade the way the backfill migration does."""

    class Meta:
        model = PonziInvestment

    scheme = SubFactory(PonziSchemeFactory)
    user = SubFactory(UserFactory)
    amount = 10
    target_tier = 1
    upgraded_at = None

    @classmethod
    def _create(
        cls, model_class: type[PonziInvestment], *args: Any, **kwargs: Any
    ) -> PonziInvestment:
        target_tier: int = kwargs.pop("target_tier")
        upgraded_at: datetime.datetime | None = kwargs.pop("upgraded_at")
        inv = super()._create(model_class, *args, **kwargs)
        T = inv.scheme.gestation_period
        for tier in range(1, target_tier + 1):
            if tier == 1:
                started_at, inferred = inv.created_at, False
            elif tier == target_tier and upgraded_at is not None:
                started_at, inferred = upgraded_at, False
            else:
                started_at, inferred = inv.created_at + (tier - 1) * T, True
            PonziTimer.objects.create(
                investment=inv, tier=tier, started_at=started_at, inferred=inferred
            )
        return inv
