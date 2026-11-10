from pathlib import Path

import pytest

HERE = Path(__file__).parent


def pytest_collection_modifyitems(items):
    # Every command test takes whole seconds and few changes touch it, so the light run leaves the suite out.
    for item in items:
        if HERE in item.path.parents:
            item.add_marker(pytest.mark.heavy)


@pytest.fixture
def debug_on(settings):
    settings.DEBUG = True
