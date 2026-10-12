import pytest


@pytest.fixture(autouse=True)
def _static_files_collected(collected_static_files):
    # Every page here renders base.html's static tags; the pure suite never pays for collectstatic (#46).
    pass
