from django.template.loader import render_to_string
from django.test import RequestFactory

PLAIN_STATIC_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"


def test_the_base_template_renders_without_the_database(settings):
    # The manifest storage needs collectstatic's output, which the pure suite never runs (#46).
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {"BACKEND": PLAIN_STATIC_STORAGE}}

    # Public pages such as the privacy policy extend it and must render with no database (#16, #49).
    page = render_to_string("base.html", request=RequestFactory().get("/"))

    assert "<main>" in page
