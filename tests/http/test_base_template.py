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
