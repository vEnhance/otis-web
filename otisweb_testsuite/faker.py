"""Custom Faker utilities for factory_boy."""

from typing import Any

import factory
import factory.random
from factory.faker import Faker

# Seed factory_boy's random generator for reproducible tests
factory.random.reseed_random("otisweb")


# waiting on https://github.com/FactoryBoy/factory_boy/pull/820 ...
class UniqueFaker(Faker):
    # based on factory.faker.Faker.generate
    def generate(self, **params: Any) -> Any:
        locale = params.pop("locale")
        subfaker = self._get_faker(locale)
        return subfaker.unique.format(self.provider, **params)
