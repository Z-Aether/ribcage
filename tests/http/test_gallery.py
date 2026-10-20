import pytest

GALLERY = "/gallery/"


@pytest.fixture
def debug(settings):
    settings.DEBUG = True


def test_the_gallery_does_not_exist_with_debug_off(client, settings):
    assert not settings.DEBUG

    assert client.get(GALLERY).status_code == 404


def test_the_gallery_renders_with_debug_on_and_no_database_queries(client, db, debug, django_assert_num_queries):
    with django_assert_num_queries(0):
        response = client.get(GALLERY)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "real_case",
    [
        pytest.param('title-card"><span class="title-card__title">Del Toro', id="a posterless film"),
        pytest.param("Winnie-the-Pooh: Blood and Honey 2", id="a long title"),
        pytest.param("La casa lobo", id="an original title that differs"),
        pytest.param('<span class="runtime__source">by hand</span>', id="a hand-entered runtime"),
        pytest.param('<span class="removed-tag">removed</span>', id="a removed suggester"),
        pytest.param("written for the gallery", id="saying the voters and notes are samples"),
    ],
)
def test_the_gallery_shows_each_real_case(client, debug, real_case):
    assert real_case in client.get(GALLERY).content.decode()


def test_the_gallery_shows_every_skin(client, debug):
    page = client.get(GALLERY).content.decode()

    for skin in ("voter", "admin", "run"):
        assert f'data-skin="{skin}"' in page
