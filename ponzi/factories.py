import datetime
from typing import Any

from factory.declarations import SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.helpers import post_generation

from core.factories import UserFactory

from .models import PonziInvestment, PonziScheme, PonziTimer


class PonziSchemeFactory(DjangoModelFactory):
    class Meta:
        model = PonziScheme

    title = Faker("bs")
    start_date = Faker("past_datetime", tzinfo=datetime.UTC)
    gestation_period = datetime.timedelta(weeks=2)


class PonziInvestmentFactory(DjangoModelFactory):
    class Meta:
        model = PonziInvestment
        skip_postgeneration_save = True

    scheme = SubFactory(PonziSchemeFactory)
    user = SubFactory(UserFactory)
    amount = 10

    @post_generation
    def timers(self, create: bool, extracted: bool, **kwargs: dict[str, Any]):
        """Log the timers the views would have, guessing any intermediate
        upgrade the same way the backfill migration does."""
        if not create:
            return
        inv: PonziInvestment = self  # type: ignore
        T = inv.scheme.gestation_period
        PonziTimer.objects.create(investment=inv, tier=1, started_at=inv.created_at)
        for tier in range(2, inv.target_tier + 1):
            if tier == inv.target_tier and inv.upgraded_at is not None:
                started_at, inferred = inv.upgraded_at, False
            else:
                started_at, inferred = inv.created_at + (tier - 1) * T, True
            PonziTimer.objects.create(
                investment=inv, tier=tier, started_at=started_at, inferred=inferred
            )
