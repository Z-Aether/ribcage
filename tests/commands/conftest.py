import pytest


@pytest.fixture
def debug_on(settings):
    settings.DEBUG = True
