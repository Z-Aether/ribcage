import pytest
from django.core.management import call_command
from django.test import override_settings


@pytest.fixture(scope="session")
def collected_static_files(tmp_path_factory):
    # Tests run with DEBUG off, where the manifest storage needs collectstatic's output (#46).
    static_root = tmp_path_factory.mktemp("staticfiles")
    with override_settings(STATIC_ROOT=static_root):
        call_command("collectstatic", interactive=False, verbosity=0)
        yield static_root
