import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.template import engines
from django.templatetags.static import static
from django.test import RequestFactory

from tests.vendored import vendored_assets

VENDORED_ASSETS = vendored_assets()


def test_the_hello_world_page_extends_the_base_template(client):
    response = client.get("/")

    assert "base.html" in [template.name for template in response.templates]
    assert "<h1>Hello World</h1>" in response.text


@pytest.mark.parametrize("name", VENDORED_ASSETS)
def test_the_base_template_loads_each_vendored_asset(client, name):
    page = client.get("/").text

    assert f'="{static(name)}"' in page


@pytest.mark.parametrize("name", VENDORED_ASSETS)
def test_the_app_serves_each_vendored_asset_with_debug_off(client, settings, name):
    assert not settings.DEBUG

    response = client.get(static(name))

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == Path(finders.find(name)).read_bytes()


def a_page_extending_the_base_template():
    child = engines["django"].from_string(
        '{% extends "base.html" %}{% block content %}<p>A child page</p>{% endblock %}'
    )
    return child.render(request=RequestFactory().get("/"))


def test_a_page_extending_the_base_template_gets_its_content_inside_main():
    page = a_page_extending_the_base_template()

    assert re.search(r"<main>\s*<p>A child page</p>\s*</main>", page)
