"""Custom Faker utilities for factory_boy."""

from typing import Any

import factory
import factory.random
from factory.builder import BuildStep, Resolver
from factory.faker import Faker

# Seed factory_boy's random generator for reproducible tests
factory.random.reseed_random("otisweb")


# waiting on https://github.com/FactoryBoy/factory_boy/pull/820 ...
class UniqueFaker(Faker):
    # based on factory.faker.Faker.evaluate
    def evaluate(
        self, instance: Resolver, step: BuildStep, extra: dict[str, Any]
    ) -> Any:
        locale = extra.pop("locale")
        subfaker = self._get_faker(locale)
        return subfaker.unique.format(self.provider, **extra)
