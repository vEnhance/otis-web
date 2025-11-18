from typing import Any

from django.contrib.sites.models import Site
from factory.declarations import LazyAttribute, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.helpers import post_generation
from wiki.models import URLPath
from wiki.models.article import Article, ArticleRevision


class ArticleRevisionFactory(DjangoModelFactory):
    class Meta:
        model = ArticleRevision

    title = Faker("text")
    content = Faker("paragraph")


class ArticleFactory(DjangoModelFactory):
    class Meta:
        model = Article
        skip_postgeneration_save = True

    @post_generation
    def set_current_revision(
        self, create: bool, extracted: Any, **kwargs: dict[str, Any]
    ):
        a: Article = self  # type: ignore
        a.current_revision = ArticleRevisionFactory(article=a)
        a.save()


class URLPathFactory(DjangoModelFactory):
    class Meta:
        model = URLPath

    article = SubFactory(ArticleFactory)
    site = LazyAttribute(lambda _: Site.objects.get_current())  # type: ignore
