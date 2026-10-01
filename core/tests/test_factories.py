from factory.base import DictFactory

from otisweb_testsuite import UniqueFaker


def test_unique_faker_actually_dedupes():
    """Guard against `UniqueFaker` silently degrading to a plain `Faker`.

    Its override has to match whatever hook factory_boy currently calls; when
    it stops matching, nothing errors, the factories just start handing out
    duplicates and unique columns blow up at random.
    """

    class TinyFactory(DictFactory):
        value = UniqueFaker("random_int", min=1000, max=1099)

    values = [TinyFactory.build()["value"] for _ in range(100)]
    assert len(set(values)) == 100
