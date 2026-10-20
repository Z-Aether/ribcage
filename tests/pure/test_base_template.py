import re

import pytest
from django.template import engines
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.test import RequestFactory

from tests.vendored import STATIC, vendored_fonts, vendored_scripts_and_styles

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


@pytest.mark.parametrize("name", vendored_scripts_and_styles())
def test_the_base_template_loads_each_vendored_asset(name):
    page = a_page_extending_the_base_template()

    assert f'="{static(name)}"' in page


def theme_stylesheets():
    page = a_page_extending_the_base_template()
    return [path for path in (STATIC / "theme").glob("*.css") if f'="{static(path.relative_to(STATIC).as_posix())}"' in page]


def test_the_base_template_loads_the_theme():
    assert theme_stylesheets()


@pytest.mark.parametrize("name", vendored_fonts())
def test_a_theme_stylesheet_the_base_template_loads_declares_each_vendored_font(name):
    declared = "".join(path.read_text(encoding="utf-8") for path in theme_stylesheets())

    assert f'url("../{name}")' in declared


def test_a_page_wears_the_voter_skin_unless_it_names_another():
    assert '<body data-skin="voter">' in a_page_extending_the_base_template()

    admin_page = engines["django"].from_string('{% extends "base.html" %}{% block skin %}admin{% endblock %}')
    assert '<body data-skin="admin">' in admin_page.render(request=RequestFactory().get("/"))
