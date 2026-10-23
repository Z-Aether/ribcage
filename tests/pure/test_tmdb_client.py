"""The TMDB client: the app's one outbound call, on the server alone, through a transport the tests fake (#5, #16, #25, #92)."""

import json
import socket
import urllib.error

import pytest

from ribcage.films import client
from ribcage.films.client import Client, NotAnswering

V3_KEY = "0123456789abcdef0123456789abcdef"
V4_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJ4In0.c2lnbmF0dXJl"


class Transport:
    def __init__(self, answer=None, error=None):
        self.answer = {"results": []} if answer is None else answer
        self.error = error
        self.requests = []

    def __call__(self, path, parameters, headers):
        self.requests.append((path, dict(parameters), dict(headers)))
        if self.error is not None:
            raise self.error
        return self.answer


def test_a_v4_read_token_goes_in_a_bearer_header():
    transport = Transport()

    Client(V4_TOKEN, transport).search("evil dead")

    _, parameters, headers = transport.requests[0]
    assert headers["Authorization"] == f"Bearer {V4_TOKEN}"
    assert "api_key" not in parameters


def test_a_v3_key_travels_as_api_key():
    transport = Transport()

    Client(V3_KEY, transport).search("evil dead")

    _, parameters, headers = transport.requests[0]
    assert parameters["api_key"] == V3_KEY
    assert "Authorization" not in headers


def test_search_asks_movie_search_alone_in_en_us():
    transport = Transport()

    Client(V3_KEY, transport).search("evil dead")

    path, parameters, _ = transport.requests[0]
    assert path == "/search/movie"
    assert (parameters["query"], parameters["language"]) == ("evil dead", "en-US")


def test_detail_asks_for_the_film_in_en_us():
    transport = Transport({"id": 109428})

    assert Client(V3_KEY, transport).detail(109428) == {"id": 109428}

    path, parameters, _ = transport.requests[0]
    assert path == "/movie/109428"
    assert parameters["language"] == "en-US"


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError(),
        socket.timeout(),
        urllib.error.HTTPError("https://api.themoviedb.org/3/search/movie", 401, "Unauthorized", None, None),
        urllib.error.URLError("no route"),
        json.JSONDecodeError("Expecting value", "", 0),
        ConnectionResetError(),
        KeyError("anything else"),
    ],
)
def test_any_failure_reads_as_tmdb_not_answering_and_names_only_the_path(error):
    with pytest.raises(NotAnswering) as raised:
        Client(V3_KEY, Transport(error=error)).search("evil dead")

    assert str(raised.value) == "TMDB failed on /search/movie."
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_an_answer_that_is_not_a_search_reads_as_not_answering():
    with pytest.raises(NotAnswering):
        Client(V3_KEY, Transport(answer=["not", "an", "object"])).search("evil dead")


def test_the_real_transport_is_plain_urllib_with_a_short_timeout(monkeypatch):
    opened = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"results": []}'

    def urlopen(request, timeout):
        opened.update(url=request.full_url, headers=dict(request.header_items()), timeout=timeout)
        return Response()

    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)

    assert client.over_the_network("/search/movie", {"query": "evil dead", "language": "en-US"}, {"accept": "application/json"}) == {"results": []}
    assert opened["url"] == "https://api.themoviedb.org/3/search/movie?query=evil+dead&language=en-US"
    assert opened["timeout"] == client.TIMEOUT_SECONDS <= 5


def test_with_debug_off_the_real_transport_is_used_even_with_recordings_installed(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setattr(client, "stand_in", Transport())

    assert client.tmdb_client().transport is client.over_the_network


def test_with_debug_on_an_installed_stand_in_answers(settings, monkeypatch):
    settings.DEBUG = True
    stand_in = Transport()
    monkeypatch.setattr(client, "stand_in", None)

    client.answer_from(stand_in)

    assert client.tmdb_client().transport is stand_in


def test_with_nothing_installed_the_real_transport_is_used(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setattr(client, "stand_in", None)

    assert client.tmdb_client().transport is client.over_the_network
