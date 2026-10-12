import re

import pytest
from django.template import engines
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.test import RequestFactory

from tests.vendored import vendored_assets

PLAIN_STATIC_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"


@pytest.fixture(autouse=True)
def _plain_static_storage(settings):
    # The manifest storage needs collectstatic's output, which the pure suite never runs (#46).
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {"BACKEND": PLAIN_STATIC_STORAGE}}


def a_page_extending_the_base_template():
    child = engines["django"].from_string(
        '{% extends "base.html" %}{% block content %}<p>A child page</p>{% endblock %}'
    )
    return child.render(request=RequestFactory().get("/"))


def test_the_base_template_renders_without_the_database():
    # Public pages such as the privacy policy extend it and must render with no database (#16, #49).
    page = render_to_string("base.html", request=RequestFactory().get("/"))

    assert "<main>" in page


def test_a_page_extending_the_base_template_gets_its_content_inside_main():
    page = a_page_extending_the_base_template()

    assert re.search(r"<main>\s*<p>A child page</p>\s*</main>", page)


@pytest.mark.parametrize("name", vendored_assets())
def test_the_base_template_loads_each_vendored_asset(name):
    page = a_page_extending_the_base_template()

    assert f'="{static(name)}"' in page
