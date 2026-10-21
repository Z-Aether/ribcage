import re

import pytest
from django.test import Client

from ribcage.identity.models import Voter

GALLERY = "/gallery/"


@pytest.fixture
def debug(settings):
    settings.DEBUG = True


@pytest.fixture
def client(client, db):
    # The gallery sits behind the login wall like any page that doesn't opt out (#58, #70).
    client.force_login(Voter.objects.create_voter("Ada"))
    return client


def notes_on_each_card(page):
    cards = re.findall(r'class="film-card__toggle"[^>]*>([^<]+)</button>(.*?)</article>', page, re.S)
    return {title: re.findall(r'<li class="(note[^"]*)"', card) for title, card in cards}


def query_table(sql):
    return re.search(r'FROM "(\w+)"', sql)[1]


def test_the_gallery_does_not_exist_with_debug_off(client, settings):
    assert not settings.DEBUG

    assert client.get(GALLERY).status_code == 404


def test_the_gallery_renders_with_debug_on_and_no_queries_beyond_the_session_and_voter_lookup(
    client, debug, django_assert_num_queries
):
    with django_assert_num_queries(2) as captured:
        response = client.get(GALLERY)

    assert response.status_code == 200
    assert [query_table(query["sql"]) for query in captured.captured_queries] == ["django_session", "identity_voter"]


def test_the_gallery_is_behind_the_login_wall(debug, db):
    assert Client().get(GALLERY).headers["Location"] == f"/login/?next={GALLERY}"


@pytest.mark.parametrize(
    "real_case",
    [
        pytest.param('title-card"><span class="title-card__title">Del Toro', id="a posterless film"),
        pytest.param("Winnie-the-Pooh: Blood and Honey 2", id="a long title"),
        pytest.param("La casa lobo", id="an original title that differs"),
        pytest.param('<span class="runtime__source">by hand</span>', id="a hand-entered runtime"),
        pytest.param(lambda page: len(notes_on_each_card(page)["Midsommar"]) > 3, id="a film with many notes"),
        pytest.param(
            lambda page: notes_on_each_card(page)["Winnie-the-Pooh: Blood and Honey 2"] == ["note note--pitch"],
            id="a film with only a pitch",
        ),
        pytest.param('<span class="removed-tag">removed</span>', id="a removed suggester"),
        pytest.param("written for the gallery", id="saying the voters and notes are samples"),
    ],
)
def test_the_gallery_shows_each_real_case(client, debug, real_case):
    page = client.get(GALLERY).content.decode()

    assert real_case(page) if callable(real_case) else real_case in page


def test_the_gallery_shows_every_skin(client, debug):
    page = client.get(GALLERY).content.decode()

    for skin in ("voter", "admin", "run"):
        assert f'data-skin="{skin}"' in page
