"""The DoesTheDogDie client: the lookup by TMDB id, the guarded retry, a record by id, and its failures (#19, #20, #32, #101).

The payloads are built inline on the shapes of the recordings, which tests never read (#56).
"""

import json
import socket
import urllib.error

import pytest

from ribcage.triggers import client
from ribcage.triggers.client import Client, NotAnswering
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount

KEY = "dtdd-key-that-must-not-leak"


def item(item_id, name, year, item_type="Movie"):
    return {"id": item_id, "name": name, "releaseYear": year, "itemTypeId": 15, "itemTypeName": item_type, "tmdbId": None}


def stat(item_id, topic_id, yes, no):
    return {"itemId": item_id, "topicId": topic_id, "topicName": f"topic {topic_id}", "yesSum": yes, "noSum": no}


def detail(listed, *counts):
    return {**listed, "topicItemStats": [stat(listed["id"], *count) for count in counts]}


class Dtdd:
    """DoesTheDogDie as the client meets it: `/items` by TMDB id or by title, and each record's detail."""

    def __init__(self, by_tmdb=(), by_title=(), details=(), remaining="29", error=None):
        self.by_tmdb = list(by_tmdb)
        self.by_title = list(by_title)
        self.details = {record["id"]: record for record in details}
        self.remaining = remaining
        self.error = error
        self.requests = []

    def __call__(self, path, parameters, headers):
        self.requests.append((path, dict(parameters), dict(headers)))
        if self.error is not None:
            raise self.error
        response_headers = {} if self.remaining is None else {"X-RateLimit-Remaining-Minute": self.remaining}
        if path == "/items" and "tmdb" in parameters:
            return self.by_tmdb, response_headers
        if path == "/items" and "q" in parameters:
            return self.by_title, response_headers
        item_id = int(path.removeprefix("/items/"))
        return self.details[item_id], response_headers


def record(listed):
    return Record(item_id=listed["id"], name=listed["name"], release_year=listed["releaseYear"], item_type=listed["itemTypeName"])


WALLYS = item(191763, "Wally's Wonderland", 2021)
WILLYS = item(752870, "Willy's Wonderland", 2021)
WILLYS_2019 = item(781758, "Willys Wonderland", 2019)
WILLYS_IN_COLOR = item(1066751, "Willy's Wonderland in Color", 2021)


def test_willys_id_lands_on_the_empty_wallys_so_the_retry_accepts_willys_of_2021_and_not_2019():
    dtdd = Dtdd(
        by_tmdb=[WALLYS],
        by_title=[WILLYS, WILLYS_2019, WILLYS_IN_COLOR],
        details=[detail(WALLYS), detail(WILLYS, (153, 2, 48), (158, 40, 0)), detail(WILLYS_2019, (153, 1, 2))],
    )

    snapshot = Client(KEY, dtdd).lookup(643586, "Willy's Wonderland", 2021).value

    assert snapshot == Snapshot(record(WILLYS), (TopicCount(153, 2, 48), TopicCount(158, 40, 0)))
    assert ("/items", {"q": "Willy's Wonderland"}) in [request[:2] for request in dtdd.requests]
    assert "/items/781758" not in [path for path, *_ in dtdd.requests]


def test_werewolf_by_nights_real_record_has_no_year_so_the_film_is_uncovered_on_its_empty_match():
    empty = item(1210242, "Werewolf By Night", 2022)
    real = item(834224, "Werewolf By Night", None)
    dtdd = Dtdd(
        by_tmdb=[empty],
        by_title=[empty, real, item(1066751, "Werewolf by Night in Color", 2023)],
        details=[detail(empty), detail(real, (153, 0, 12), (158, 3, 4))],
    )

    snapshot = Client(KEY, dtdd).lookup(894205, "Werewolf by Night", 2022).value

    assert snapshot == Snapshot(record(empty), ())
    assert snapshot.is_uncovered
    assert "/items/834224" not in [path for path, *_ in dtdd.requests]


def test_arachnophobias_tv_show_collision_is_filtered_out_before_any_detail_is_fetched():
    movie = item(8740, "Arachnophobia", 1990)
    show = item(603231, "That's Entertainment", None, item_type="TV Show")
    dtdd = Dtdd(by_tmdb=[show, movie], details=[detail(show, (153, 50, 0)), detail(movie, (153, 0, 30))])

    snapshot = Client(KEY, dtdd).lookup(6488, "Arachnophobia", 1990).value

    assert snapshot.record == record(movie)
    assert [path for path, *_ in dtdd.requests] == ["/items", "/items/8740"]


def test_of_infesteds_two_movie_records_the_one_with_more_voted_topics_wins():
    fewer = item(1116075, "Infested", 2023)
    more = item(1071843, "Infested", 2023)
    dtdd = Dtdd(
        by_tmdb=[fewer, more],
        details=[detail(fewer, (153, 1, 0)), detail(more, (153, 1, 0), (158, 0, 2), (160, 4, 4))],
    )

    assert Client(KEY, dtdd).lookup(1043041, "Infested", 2023).value.record == record(more)


@pytest.mark.parametrize("real_first", [True, False], ids=["recorded_order", "reversed"])
def test_buddys_second_empty_movie_record_never_wins_whichever_comes_first(real_first):
    real = item(821957, "Buddy", 2026)
    empty = item(1533045, "Buddy", 2026)
    dtdd = Dtdd(by_tmdb=[real, empty] if real_first else [empty, real], details=[detail(empty), detail(real, (153, 0, 3))])

    snapshot = Client(KEY, dtdd).lookup(1218925, "Buddy", 2026).value

    assert snapshot == Snapshot(record(real), (TopicCount(153, 0, 3),))
    assert [path for path, *_ in dtdd.requests if path == "/items"] == ["/items"]


def test_an_id_and_a_retry_that_find_nothing_leave_the_film_uncovered_with_no_match():
    snapshot = Client(KEY, Dtdd()).lookup(1, "Nothing Like It", 2024).value

    assert snapshot == Snapshot(None, ())
    assert snapshot.is_uncovered


def test_a_topic_without_a_vote_is_no_topic_count():
    listed = item(8740, "Arachnophobia", 1990)
    dtdd = Dtdd(by_tmdb=[listed], details=[detail(listed, (153, 0, 0), (158, 2, 0))])

    assert Client(KEY, dtdd).lookup(6488, "Arachnophobia", 1990).value.counts == (TopicCount(158, 2, 0),)


def test_a_film_without_a_year_accepts_nothing_on_the_retry():
    yearless = item(834224, "Werewolf By Night", None)
    dtdd = Dtdd(by_title=[yearless], details=[detail(yearless, (153, 1, 0))])

    assert Client(KEY, dtdd).lookup(894205, "Werewolf by Night", None).value == Snapshot(None, ())


@pytest.mark.parametrize("item_type", ["Movie", "TV Show"])
def test_a_record_fetched_by_id_gives_its_snapshot_whatever_its_item_type(item_type):
    listed = item(10101, "Surprise", 2019, item_type=item_type)
    dtdd = Dtdd(details=[detail(listed, (153, 3, 1))])

    snapshot = Client(KEY, dtdd).record(10101).value

    assert snapshot == Snapshot(record(listed), (TopicCount(153, 3, 1),))
    assert [path for path, *_ in dtdd.requests] == ["/items/10101"]


def test_every_answer_reports_the_remaining_minute_count_after_its_last_call():
    listed = item(8740, "Arachnophobia", 1990)
    dtdd = Dtdd(by_tmdb=[listed], details=[detail(listed, (153, 0, 30))], remaining="7")

    assert Client(KEY, dtdd).lookup(6488, "Arachnophobia", 1990).remaining == 7
    assert Client(KEY, dtdd).record(8740).remaining == 7


def test_an_answer_without_the_header_reads_as_no_limit_in_sight():
    listed = item(8740, "Arachnophobia", 1990)

    assert Client(KEY, Dtdd(details=[detail(listed)], remaining=None)).record(8740).remaining is None


def test_the_key_travels_only_in_the_x_api_key_header():
    listed = item(8740, "Arachnophobia", 1990)
    dtdd = Dtdd(by_tmdb=[listed], details=[detail(listed)])

    Client(KEY, dtdd).lookup(6488, "Arachnophobia", 1990)

    assert {headers["X-API-KEY"] for *_, headers in dtdd.requests} == {KEY}
    assert all(KEY not in path and KEY not in json.dumps(parameters) for path, parameters, _ in dtdd.requests)


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError(),
        socket.timeout(),
        urllib.error.HTTPError(f"{client.DTDD_API}/items/8740", 401, "Unauthorized", None, None),
        urllib.error.HTTPError(f"{client.DTDD_API}/items/8740", 503, "Service Unavailable", None, None),
        urllib.error.HTTPError(f"{client.DTDD_API}/items/8740", 429, "Too Many Requests", None, None),
        urllib.error.URLError("no route"),
        json.JSONDecodeError("Expecting value", "", 0),
    ],
)
def test_any_failure_raises_not_answering_naming_the_path_and_never_the_key(error):
    with pytest.raises(NotAnswering) as raised:
        Client(KEY, Dtdd(error=error)).record(8740)

    assert str(raised.value) == "DoesTheDogDie failed on /items/8740."
    assert KEY not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_a_404_raises_no_such_record_which_every_other_caller_reads_as_not_answering():
    # A pasted link's refusal tells a record that isn't there from an outage; the refresh still reads it as a failure (#105).
    missing = urllib.error.HTTPError(f"{client.DTDD_API}/items/8740", 404, "Not Found", None, None)

    with pytest.raises(client.NoSuchRecord) as raised:
        Client(KEY, Dtdd(error=missing)).record(8740)

    assert isinstance(raised.value, NotAnswering)
    assert KEY not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


@pytest.mark.parametrize(
    "malformed",
    [
        ["not", "a", "record"],
        {"id": 8740, "name": "Arachnophobia", "releaseYear": 1990, "itemTypeName": "Movie"},
        {**item(8740, "Arachnophobia", 1990), "topicItemStats": [{"topicId": 153, "yesSum": "many"}]},
    ],
)
def test_a_malformed_record_raises_not_answering(malformed):
    dtdd = Dtdd()
    dtdd.details[8740] = malformed

    with pytest.raises(NotAnswering, match="/items/8740"):
        Client(KEY, dtdd).record(8740)


@pytest.mark.parametrize("malformed", [{"items": []}, [{"id": "8740"}], ["Arachnophobia"]])
def test_a_malformed_list_of_items_raises_not_answering(malformed):
    with pytest.raises(NotAnswering, match="/items"):
        Client(KEY, Dtdd(by_tmdb=malformed)).lookup(6488, "Arachnophobia", 1990)


def test_the_real_transport_is_plain_urllib_with_the_key_in_a_header_and_a_five_second_timeout(monkeypatch):
    opened = {}

    class Response:
        headers = {"x-ratelimit-remaining-minute": "28"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"[]"

    def urlopen(request, timeout):
        opened.update(url=request.full_url, headers=dict(request.header_items()), timeout=timeout)
        return Response()

    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)

    answer = Client(KEY).lookup(6488, "Arachnophobia", 1990)

    assert answer.remaining == 28
    assert opened["url"] == "https://www.doesthedogdie.com/api/v3/items?q=Arachnophobia"
    assert KEY not in opened["url"]
    assert opened["headers"]["X-api-key"] == KEY
    assert opened["timeout"] == client.TIMEOUT_SECONDS == 5


def test_with_debug_off_the_real_transport_is_used_even_with_a_stand_in_installed(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setattr(client, "stand_in", Dtdd())

    assert client.dtdd_client().transport is client.over_the_network


def test_with_debug_on_an_installed_stand_in_answers(settings, monkeypatch):
    settings.DEBUG = True
    stand_in = Dtdd()
    monkeypatch.setattr(client, "stand_in", None)

    client.answer_from(stand_in)

    assert client.dtdd_client().transport is stand_in
