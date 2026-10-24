from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from tests.vendored import vendored_assets


@pytest.mark.parametrize("name", vendored_assets())
def test_the_app_serves_each_vendored_asset_with_debug_off(client, settings, name):
    assert not settings.DEBUG

    response = client.get(static(name))

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == Path(finders.find(name)).read_bytes()


@pytest.mark.parametrize("name", ["theme/theme.css", "theme/pumpkin.svg", "components/film-card.js", "components/voter-menu.js", "components/bat.js", "shell/as-it-is-now.js"])
def test_the_app_serves_the_themes_own_files_with_debug_off(client, settings, name):
    assert not settings.DEBUG

    assert client.get(static(name)).status_code == 200
