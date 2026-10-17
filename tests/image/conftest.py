import pytest

from tests.image.docker import REPO_ROOT, docker

IMAGE = "ribcage:pytest"


@pytest.fixture(scope="session")
def image():
    docker("build", "--platform", "linux/amd64", "--tag", IMAGE, str(REPO_ROOT))
    return IMAGE
