"""Correcting a match, its pure parts: the item id a pasted link names, the search link, and the snapshot carried signed (#105)."""

import pytest

from ribcage.triggers import correction
from ribcage.triggers.dtdd import Record, Snapshot, TopicCount

WEREWOLF = Snapshot(Record(834224, "Werewolf by Night", None, "Movie"), (TopicCount(153, 9, 0), TopicCount(200, 3, 4)))


@pytest.mark.parametrize(
    "link",
    [
        "https://www.doesthedogdie.com/media/834224",
        "https://www.doesthedogdie.com/media/834224/",
        "http://doesthedogdie.com/media/834224",
        "www.doesthedogdie.com/media/834224",
        "  https://www.DoesTheDogDie.com/media/834224?ref=search#topics  ",
    ],
)
def test_a_dtdd_item_page_names_its_item_id_however_it_was_copied(link):
    assert correction.item_id_in(link) == 834224


@pytest.mark.parametrize(
    "link",
    [
        "",
        "Werewolf by Night",
        "834224",
        "https://www.imdb.com/title/tt15318872/",
        "https://www.doesthedogdie.com/search?q=werewolf",
        "https://www.doesthedogdie.com/media/",
        "https://www.doesthedogdie.com/media/0",
        "https://www.doesthedogdie.com/media/abc",
        "https://doesthedogdie.com.example.org/media/834224",
        "https://example.org/www.doesthedogdie.com/media/834224",
        "ftp://www.doesthedogdie.com/media/834224",
        "javascript:alert(1)//www.doesthedogdie.com/media/834224",
        "https://[::1/media/834224",
    ],
)
def test_anything_else_is_refused_as_not_a_dtdd_link(link):
    with pytest.raises(correction.Refused) as refused:
        correction.item_id_in(link)

    assert str(refused.value) == correction.NOT_A_LINK


def test_find_it_opens_dtdds_home_page_whose_first_field_is_its_search():
    # Its search answers by script alone: /search?q= redirects a page load to the home page (checked live, 2026-10-24).
    assert correction.offered("/dtdd/match/").search == "https://www.doesthedogdie.com/"


def test_a_signed_snapshot_reads_back_exactly_for_the_film_it_was_fetched_for():
    assert correction.unsigned(correction.signed(WEREWOLF, 7), 7) == WEREWOLF


def test_another_films_signed_snapshot_is_tampered():
    with pytest.raises(correction.Tampered):
        correction.unsigned(correction.signed(WEREWOLF, 7), 8)


def altered(value):
    middle = len(value) // 3
    return value[:middle] + ("A" if value[middle] != "A" else "B") + value[middle + 1 :]


@pytest.mark.parametrize(
    "value",
    [altered(correction.signed(WEREWOLF, 7)), correction.signed(WEREWOLF, 7)[:-3], "", "not signed at all"],
    ids=["altered", "cut short", "empty", "never signed"],
)
def test_an_altered_or_unsigned_snapshot_is_tampered(value):
    with pytest.raises(correction.Tampered):
        correction.unsigned(value, 7)
