"""Find: a trailing year narrows TMDB's title search to that year ±1, on the server (#21, #57, #61, #92)."""

import pytest

from ribcage.films.find import PICKER_SIZE, Query, find, parsed


def a_result(tmdb_id, title, release_date):
    return {"id": tmdb_id, "title": title, "original_title": title, "release_date": release_date, "poster_path": None}


class Search:
    """TMDB's title search as a fake: the answers it gives by title, and the titles it was asked for."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def __call__(self, title):
        self.asked.append(title)
        return {"results": self.answers.get(title, []), "total_results": len(self.answers.get(title, []))}


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("the thing 1982", Query("the thing", 1982)),
        ("  the   thing   1982 ", Query("the thing", 1982)),
        ("the thing (1982)", Query("the thing", 1982)),
        ("the thing", Query("the thing", None)),
        ("Blade Runner 2049", Query("Blade Runner", 2049)),
        ("ringu1998", Query("ringu1998", None)),
        ("the thing 82", Query("the thing 82", None)),
        ("the thing 19821", Query("the thing 19821", None)),
    ],
)
def test_a_trailing_year_is_parsed_from_the_title(text, query):
    assert parsed(text) == query


@pytest.mark.parametrize("text", ["1922", " 2049 ", "(1982)"])
def test_a_query_that_is_only_a_year_is_a_title(text):
    assert parsed(text) == Query(text.strip(), None)


def test_a_trailing_year_narrows_the_title_search_to_that_year_and_one_either_side():
    search = Search(
        {
            "insidious": [
                a_result(1, "Insidious: Out of the Further", "2026-08-19"),
                a_result(2, "Insidious", "2011-03-31"),
                a_result(3, "Insidious", "2009-01-01"),
                a_result(4, "Insidious Twin", "2010-06-01"),
                a_result(5, "Insidious: Chapter 2", "2013-09-12"),
                a_result(6, "Insidious Rewind", ""),
                a_result(7, "Insidious", "2008-05-01"),
            ]
        }
    )

    assert [result.tmdb_id for result in find("insidious 2010", search)] == [2, 3, 4]
    assert search.asked == ["insidious"]


def test_without_a_year_the_first_five_results_come_in_tmdbs_order():
    results = [a_result(n, f"Film {n}", "2000-01-01") for n in range(1, 9)]

    found = find("film", Search({"film": results}))

    assert [result.tmdb_id for result in found] == [1, 2, 3, 4, 5]
    assert PICKER_SIZE == 5


def test_a_title_ending_in_a_number_still_finds_its_film_when_narrowing_leaves_nothing():
    search = Search(
        {
            "Blade Runner": [a_result(78, "Blade Runner", "1982-06-25"), a_result(335984, "Blade Runner 2049", "2017-10-04")],
            "Blade Runner 2049": [a_result(335984, "Blade Runner 2049", "2017-10-04")],
        }
    )

    found = find("Blade Runner 2049", search)

    assert [result.tmdb_id for result in found] == [335984]
    assert search.asked == ["Blade Runner", "Blade Runner 2049"]


def test_a_year_only_query_is_searched_as_a_title():
    search = Search({"1922": [a_result(452522, "1922", "2017-10-20")]})

    assert [result.tmdb_id for result in find("1922", search)] == [452522]
    assert search.asked == ["1922"]


def test_no_results_is_an_empty_picker():
    assert find("cabinet of curiosities", Search({})) == ()


def test_a_blank_query_searches_nothing():
    search = Search({})

    assert find("   ", search) == ()
    assert search.asked == []


def test_a_year_that_narrows_to_more_than_five_results_shows_the_first_five_in_tmdbs_order():
    results = [a_result(n, f"Film {n}", "2010-01-01") for n in range(1, 9)]

    found = find("film 2010", Search({"film": results}))

    assert [result.tmdb_id for result in found] == [1, 2, 3, 4, 5]
