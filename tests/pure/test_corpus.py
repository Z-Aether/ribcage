import dataclasses
import json
import shutil
import unicodedata

import pytest

from ribcage.films import corpus
from ribcage.films.film import Film, RuntimeSource

NO_YEAR_ENTRIES = {"Sissy", "Sting", "Escape Room", "Time Lapse", "Zoombies", "Brightburn"}
CABINET = "Del Toro's Cabinet of Curiosities"
MAD_GOD = "Phil Tippet's Mad God"


@pytest.fixture(scope="module")
def committed_films(tmp_path_factory):
    # Only the committed files are copied, so these tests can never lean on the gitignored DTDD payloads (#40).
    directory = tmp_path_factory.mktemp("films")
    shutil.copy(corpus.CORPUS_DIRECTORY / corpus.CORPUS_LIST, directory)
    shutil.copytree(corpus.CORPUS_DIRECTORY / corpus.TMDB_RECORDINGS, directory / corpus.TMDB_RECORDINGS)
    return directory


@pytest.fixture(scope="module")
def recorded(committed_films):
    return {film.entry.written_title: film for film in corpus.read_corpus(committed_films)}


def coverage_measurement():
    measured = json.loads((corpus.CORPUS_DIRECTORY / "results.json").read_text(encoding="utf-8"))
    return {row["title"]: row for row in measured if row.get("title")}


def test_the_corpus_holds_fifty_films_each_recorded_once(recorded):
    assert len(recorded) == 50
    tmdb_ids = [film.entry.tmdb_id for film in recorded.values() if film.entry.tmdb_id]
    assert len(tmdb_ids) == len(set(tmdb_ids)) == 49


def test_the_entries_kept_from_the_coverage_run_keep_its_tmdb_ids_except_mad_god(recorded):
    measured = coverage_measurement()
    kept = {title: film for title, film in recorded.items() if title in measured}

    assert len(kept) == 38
    assert {title for title, film in kept.items() if film.entry.tmdb_id != measured[title].get("id")} == {MAD_GOD}


def test_mad_god_is_phil_tippetts_film_not_the_ghoul_log_short_the_coverage_run_picked_by_year(recorded):
    mad_god = recorded[MAD_GOD].film

    assert coverage_measurement()[MAD_GOD]["pick"] == "Mad God Ghoul Log (2022)"
    assert (mad_god.title, mad_god.year, mad_god.directors) == ("Mad God", 2021, ("Phil Tippett",))


def test_exactly_six_entries_carry_no_year_and_a_person_still_picked_each(recorded):
    no_year = {title for title, film in recorded.items() if film.entry.written_year is None}

    assert no_year == NO_YEAR_ENTRIES
    assert all(recorded[title].film.tmdb_id for title in no_year)


@pytest.mark.parametrize("title", ["Escape Room", "Triangle", "The Invisible Man", "Cube", "Good Boy"])
def test_one_search_returns_several_films_of_exactly_the_title_written(recorded, title):
    exact = [result.tmdb_id for result in recorded[title].search_results if result.title == title]

    assert len(exact) >= 5
    assert recorded[title].entry.tmdb_id in exact


def test_evil_dead_searches_to_evil_dead_burn_first_while_the_group_meant_the_2013_film(recorded):
    results = recorded["Evil Dead"].search_results

    assert (results[0].title, results[0].year) == ("Evil Dead Burn", 2026)
    assert (recorded["Evil Dead"].film.title, recorded["Evil Dead"].film.year) == ("Evil Dead", 2013)
    assert recorded["Evil Dead"].film.tmdb_id != results[0].tmdb_id


def test_willys_wonderland_is_unambiguous_on_tmdb_and_its_id_landed_on_wallys_on_doesthedogdie(recorded):
    willys = recorded["Willy's Wonderland"]

    assert [(result.tmdb_id, result.title) for result in willys.search_results] == [(643586, "Willy's Wonderland")]
    measured = coverage_measurement()["Willy's Wonderland"]
    assert (measured["id"], measured["dtddName"]) == (willys.film.tmdb_id, "Wally's Wonderland")


def test_nightbreed_is_recorded_at_tmdbs_one_runtime_though_the_group_asked_for_the_directors_cut(recorded):
    nightbreed = recorded["Nightbreed (directors cut)"]

    assert nightbreed.search_results == ()
    assert (nightbreed.film.runtime, nightbreed.film.runtime_source) == (102, RuntimeSource.TMDB)
    # A year earlier TMDB said 121 for the same film: the runtime is a fact about a copy, never settled (#5).
    assert coverage_measurement()["Nightbreed (directors cut)"]["runtime"] == 121


def test_cabinet_of_curiosities_is_the_hand_entered_film_it_will_be(recorded):
    cabinet = recorded[CABINET]

    assert cabinet.search_results == ()
    assert cabinet.film.tmdb_id is None
    assert cabinet.film.poster_path is None
    assert (cabinet.film.title, cabinet.film.year) == (CABINET, 2022)
    assert (cabinet.film.runtime, cabinet.film.runtime_source) == (47, RuntimeSource.HAND_ENTERED)


def test_maramas_macron_survives_the_round_trip(recorded, committed_films):
    marama = recorded["Mārama"]

    assert marama.film.title == marama.film.original_title == "Mārama"
    assert unicodedata.is_normalized("NFC", marama.film.title)
    assert "Mārama".encode() in (committed_films / corpus.CORPUS_LIST).read_bytes()
    assert marama.entry.recording_name == "marama-2025"


def test_a_tmdb_film_reads_into_every_field_the_card_shows(recorded):
    assert recorded["Infested / Vermines"].film == Film(
        tmdb_id=1063879,
        title="Infested",
        original_title="Vermines",
        year=2023,
        directors=("Sébastien Vaniček",),
        certificate="NR",
        trailer_key="LR-uiy20_zM",
        runtime=106,
        runtime_source=RuntimeSource.TMDB,
        poster_path="/dY98PkUAbIGUUg0FhXEcOkbzHIZ.jpg",
        imdb_id="tt26744289",
    )


def test_film_data_carries_no_official_synopsis_or_genres():
    fields = {field.name for field in dataclasses.fields(Film)}

    assert not fields & {"overview", "synopsis", "genres", "tagline"}


def test_without_the_dtdd_payloads_every_film_says_so_and_reading_one_fails_plainly(recorded, committed_films):
    assert not any(film.dtdd_recorded for film in recorded.values())

    with pytest.raises(corpus.DtddNotRecorded, match="gitignored under DTDD's terms, so a fresh clone has none"):
        corpus.read_dtdd(recorded["Midsommar"].entry, committed_films)


def test_a_hand_entered_film_was_never_looked_up_on_doesthedogdie(recorded, committed_films):
    with pytest.raises(corpus.DtddNotRecorded, match="hand-entered, so nothing was looked up"):
        corpus.read_dtdd(recorded[CABINET].entry, committed_films)


def test_a_recorded_dtdd_payload_is_present_and_read_back_raw(committed_films, tmp_path):
    shutil.copytree(committed_films, tmp_path, dirs_exist_ok=True)
    midsommar = next(entry for entry in corpus.read_entries(tmp_path) if entry.written_title == "Midsommar")
    payload = {"lookup": [{"id": 1, "name": "Midsommar"}], "retry": None, "items": {"1": {"topicItemStats": []}}}
    (tmp_path / corpus.DTDD_RECORDINGS).mkdir()
    (tmp_path / corpus.DTDD_RECORDINGS / f"{midsommar.recording_name}.json").write_text(json.dumps(payload))

    films = {film.entry.written_title: film for film in corpus.read_corpus(tmp_path)}

    assert films["Midsommar"].dtdd_recorded
    assert not films["The Thing"].dtdd_recorded
    assert corpus.read_dtdd(midsommar, tmp_path) == payload
