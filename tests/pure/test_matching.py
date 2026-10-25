"""A viewer's matched topics and the ring, pure over a watched list and a snapshot (#20 §3-§4, #111)."""

from django.template.loader import render_to_string

from ribcage.films.card import Matched, TopicRow
from ribcage.triggers.dtdd import TopicCount
from ribcage.triggers.matching import matched
from tests.pure.test_dtdd_section import VOCABULARY

DOGS, CATS, JUMPS = 153, 158, 200


def test_a_thin_match_is_listed_with_its_counts_and_no_ring():
    assert matched((TopicCount(DOGS, 1, 0),), VOCABULARY, {DOGS}) == Matched((TopicRow("dogs dying", 1, 0),), ring=False)


def test_five_yes_and_no_no_rings(settings):
    assert matched((TopicCount(DOGS, 5, 0),), VOCABULARY, {DOGS}).ring


def test_five_yes_and_five_no_is_listed_without_a_ring(settings):
    found = matched((TopicCount(DOGS, 5, 5),), VOCABULARY, {DOGS})

    assert found.rows == (TopicRow("dogs dying", 5, 5),)
    assert not found.ring


def test_a_ticked_topic_the_film_lacks_never_matches():
    assert matched((TopicCount(CATS, 9, 0),), VOCABULARY, {DOGS}) is None


def test_an_empty_list_matches_nothing():
    assert matched((TopicCount(DOGS, 9, 0),), VOCABULARY, set()) is None


def test_a_film_with_no_counts_matches_nothing():
    assert matched((), VOCABULARY, {DOGS}) is None


def test_the_ring_needs_only_one_carried_topic_and_the_rows_list_the_most_yes_first(settings):
    found = matched((TopicCount(DOGS, 2, 0), TopicCount(CATS, 7, 1), TopicCount(JUMPS, 9, 0)), VOCABULARY, {DOGS, CATS})

    assert [row.label for row in found.rows] == ["cats dying", "dogs dying"]
    assert found.ring


def test_a_ticked_topic_with_no_yes_vote_or_outside_the_vocabulary_is_not_a_matched_topic():
    assert matched((TopicCount(DOGS, 0, 4), TopicCount(999, 9, 0)), VOCABULARY, {DOGS, 999}) is None


def test_the_matched_block_is_a_part_of_its_own_listing_every_row_with_raw_counts():
    shown = render_to_string("components/dtdd_matched.html", {"matched": Matched((TopicRow("dogs dying", 3, 1), TopicRow("jump scares", 1, 0)), ring=False)})

    assert "dogs dying</span> — <span class=\"dtdd__counts\">3 yes / 1 no" in shown
    assert "jump scares</span> — <span class=\"dtdd__counts\">1 yes / 0 no" in shown
