import io
import json
import urllib.error
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from ribcage.films import corpus
from ribcage.seeding.management.commands import fetchcorpus

TMDB_KEY = "tmdb-key-that-must-not-leak"
DTDD_KEY = "dtdd-key-that-must-not-leak"
ENTRIES = [
    {"written_title": "Willy's Wonderland", "written_year": 2021, "tmdb_id": 643586},
    {"written_title": "Del Toro's Cabinet of Curiosities", "written_year": 2022, "tmdb_id": None, "runtime": 47},
]


def tmdb_detail(tmdb_id, title, poster_path):
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": title,
        "release_date": "2021-02-12",
        "runtime": 89,
        "poster_path": poster_path,
        "imdb_id": "tt13759970",
        "credits": {"crew": []},
        "videos": {"results": []},
        "release_dates": {"results": []},
    }


class FakeApis:
    """TMDB and DoesTheDogDie as the fetch meets them, with Willy's id landing on DTDD's empty Wally's record (#19)."""

    def __init__(self):
        self.requests = []

    def __call__(self, service, base, path, parameters, headers):
        self.requests.append((service, path, dict(parameters), dict(headers)))
        if path == "/search/movie":
            return {"page": 1, "results": [], "total_results": 0}
        if path == "/movie/643586":
            return tmdb_detail(643586, "Willy's Wonderland", None)
        if path == "/items" and "tmdb" in parameters:
            return [{"id": 191763, "name": "Wally's Wonderland", "releaseYear": 2021}]
        if path == "/items" and "q" in parameters:
            return [
                {"id": 752870, "name": "Willy's Wonderland", "releaseYear": 2021},
                {"id": 781758, "name": "Willys Wonderland", "releaseYear": 2019},
                {"id": 1066751, "name": "Willy's Wonderland in Color", "releaseYear": 2021},
            ]
        if path == "/items/191763":
            return {"item": {"id": 191763}, "topicItemStats": []}
        if path == "/items/752870":
            return {"item": {"id": 752870}, "topicItemStats": [{"topicName": "a dog dies", "yesSum": 9, "noSum": 1}]}
        if path == "/items/781758":
            return {"item": {"id": 781758}, "topicItemStats": []}
        raise AssertionError(f"unexpected request {service} {path}")


@pytest.fixture
def films_directory(tmp_path, monkeypatch, settings):
    settings.TMDB_API_KEY = TMDB_KEY
    settings.DTDD_API_KEY = DTDD_KEY
    (tmp_path / corpus.CORPUS_LIST).write_text(json.dumps(ENTRIES), encoding="utf-8")
    monkeypatch.setattr(corpus, "CORPUS_DIRECTORY", tmp_path)
    monkeypatch.setattr(fetchcorpus, "DTDD_SECONDS_BETWEEN_CALLS", 0)
    return tmp_path


@pytest.fixture
def apis(monkeypatch):
    fake = FakeApis()
    monkeypatch.setattr(fetchcorpus, "get_json", fake)
    return fake


def recorded_files(directory):
    return {path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8") for path in directory.rglob("*.json")}


def test_with_debug_off_it_refuses_and_fetches_nothing(films_directory, apis, settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="only with DEBUG on"):
        call_command("fetchcorpus")

    assert apis.requests == []
    assert set(recorded_files(films_directory)) == {corpus.CORPUS_LIST}


def test_it_records_tmdb_and_dtdd_for_each_entry_and_only_searches_a_hand_entered_one(films_directory, apis, debug_on):
    call_command("fetchcorpus", stdout=StringIO())

    assert set(recorded_files(films_directory)) == {
        corpus.CORPUS_LIST,
        "tmdb/willy-s-wonderland-2021.json",
        "tmdb/del-toro-s-cabinet-of-curiosities-2022.json",
        "dtdd/willy-s-wonderland-2021.json",
    }
    cabinet = json.loads((films_directory / "tmdb/del-toro-s-cabinet-of-curiosities-2022.json").read_text())
    assert cabinet["detail"] is None
    assert ("TMDB", "/search/movie", {"query": "Del Toro's Cabinet of Curiosities", "language": "en-US", "api_key": TMDB_KEY}) in [
        request[:3] for request in apis.requests
    ]


def test_an_empty_id_match_is_retried_by_title_recording_every_item_of_the_same_name(
    films_directory, apis, debug_on
):
    call_command("fetchcorpus", stdout=StringIO())

    recording = corpus.read_dtdd(corpus.read_entries(films_directory)[0], films_directory)
    assert [item["name"] for item in recording["lookup"]] == ["Wally's Wonderland"]
    assert [item["id"] for item in recording["retry"]] == [752870, 781758, 1066751]
    assert set(recording["items"]) == {"191763", "752870", "781758"}


def test_the_keys_come_from_the_settings_and_reach_no_recording_or_output(films_directory, apis, debug_on):
    output = StringIO()

    call_command("fetchcorpus", stdout=output)

    assert {request[2].get("api_key") for request in apis.requests if request[0] == "TMDB"} == {TMDB_KEY}
    assert {request[3]["X-API-KEY"] for request in apis.requests if request[0] == "DoesTheDogDie"} == {DTDD_KEY}
    written = "".join(recorded_files(films_directory).values()) + output.getvalue()
    assert TMDB_KEY not in written
    assert DTDD_KEY not in written


def test_a_v4_read_token_travels_as_a_bearer_header_rather_than_in_the_url(films_directory, apis, debug_on, settings):
    settings.TMDB_API_KEY = "header.payload.signature"

    call_command("fetchcorpus", stdout=StringIO())

    tmdb_requests = [request for request in apis.requests if request[0] == "TMDB"]
    assert all("api_key" not in parameters for _, _, parameters, _ in tmdb_requests)
    assert {headers["Authorization"] for *_, headers in tmdb_requests} == {"Bearer header.payload.signature"}


def test_a_rerun_replaces_the_recorded_files_and_leaves_the_coverage_measurement_alone(films_directory, apis, debug_on):
    (films_directory / "results.json").write_text("#19's measurement", encoding="utf-8")
    call_command("fetchcorpus", stdout=StringIO())
    first = recorded_files(films_directory)
    (films_directory / "tmdb" / "dropped-from-the-corpus.json").write_text("{}", encoding="utf-8")

    call_command("fetchcorpus", stdout=StringIO())

    assert recorded_files(films_directory) == first
    assert (films_directory / "results.json").read_text(encoding="utf-8") == "#19's measurement"


def test_it_names_the_posterless_films_it_finds(films_directory, apis, debug_on):
    output = StringIO()

    call_command("fetchcorpus", stdout=output)

    assert "Posterless: Willy's Wonderland (2021)" in output.getvalue()


def test_a_failed_request_writes_nothing_and_its_error_names_no_key(films_directory, debug_on, monkeypatch, settings):
    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO())

    monkeypatch.setattr(fetchcorpus.urllib.request, "urlopen", refuse)

    with pytest.raises(CommandError) as refusal:
        call_command("fetchcorpus", stdout=StringIO())

    assert "401" in str(refusal.value)
    assert TMDB_KEY not in str(refusal.value)
    assert set(recorded_files(films_directory)) == {corpus.CORPUS_LIST}


def test_a_server_error_is_tried_again_before_the_fetch_gives_up(monkeypatch):
    monkeypatch.setattr(fetchcorpus, "SECONDS_BEFORE_ANOTHER_ATTEMPT", 0)
    answers = iter([urllib.error.HTTPError("https://example.invalid", 502, "Bad Gateway", {}, io.BytesIO())])

    def flaky(request, timeout):
        for answer in answers:
            raise answer
        return io.BytesIO(b'{"page": 1, "results": [], "total_results": 0}')

    monkeypatch.setattr(fetchcorpus.urllib.request, "urlopen", flaky)

    assert fetchcorpus.get_json("TMDB", "https://api.themoviedb.org/3", "/search/movie", {}, {}) == {
        "page": 1,
        "results": [],
        "total_results": 0,
    }
