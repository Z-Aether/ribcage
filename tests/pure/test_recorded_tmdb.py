"""The seeded instance's TMDB: the recordings in fixtures/films/ answer, and anything unrecorded reads as an outage (#57, #92)."""

import pytest

from ribcage.films.client import Client, NotAnswering
from ribcage.seeding.recorded import RecordedTmdb

KEY = "your-tmdb-api-key"


@pytest.fixture(scope="module")
def recorded():
    return Client(KEY, RecordedTmdb())


def test_a_search_by_a_written_title_is_answered_from_its_recording(recorded):
    answer = recorded.search("Evil Dead")

    assert [result["id"] for result in answer["results"][:2]] == [1212763, 109428]


def test_a_search_matches_the_written_title_whatever_its_case_and_spacing(recorded):
    assert recorded.search("  evil   DEAD ") == recorded.search("Evil Dead")


def test_a_detail_is_answered_from_its_recording_by_tmdb_id(recorded):
    detail = recorded.detail(109428)

    assert (detail["id"], detail["title"]) == (109428, "Evil Dead")


def test_cabinet_of_curiosities_is_recorded_as_one_result_with_none_listed(recorded):
    answer = recorded.search("Del Toro's Cabinet of Curiosities")

    assert (answer["total_results"], answer["results"]) == (1, [])


@pytest.mark.parametrize("ask", [lambda client: client.search("blade runner 2049"), lambda client: client.detail(78)])
def test_anything_unrecorded_reads_as_tmdb_not_answering(recorded, ask):
    with pytest.raises(NotAnswering):
        ask(recorded)
