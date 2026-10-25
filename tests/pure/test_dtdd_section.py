"""The film card's DoesTheDogDie section as plain data: each state, the topics grouped and ordered, and the credit (#20, #21, #103)."""

import re
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from django.template.loader import render_to_string

from ribcage.films.card import DtddMatch, FilmCard, TopicGroup, TopicRow
from ribcage.triggers.dtdd import NO_MATCH, Record, Snapshot, TopicCount
from ribcage.triggers.section import GAPS, section
from ribcage.triggers.status import Fetched, State, Status
from ribcage.triggers.vocabulary import UNCATEGORIZED, SuperCategory, Topic, Vocabulary
from tests.films import THE_SHINING

AT = datetime(2026, 10, 24, 18, 30, tzinfo=UTC)
ANIMALS = SuperCategory(54, "Animals")
VIOLENCE = SuperCategory(50, "Violence")
VOCABULARY = Vocabulary(
    topics=(
        Topic(153, "dogs dying", "", "", ANIMALS),
        Topic(158, "cats dying", "", "", ANIMALS),
        Topic(161, "horses dying", "", "", ANIMALS),
        Topic(200, "jump scares", "", "", UNCATEGORIZED),
        Topic(300, "gun violence", "", "", VIOLENCE),
    ),
    # DoesTheDogDie's own order, which the My warnings page uses: Violence before Animals here.
    super_categories=(VIOLENCE, ANIMALS),
)
WILLYS = Record(5381, "Willy's Wonderland", 2021, "Movie")
CREDIT = '<a href="https://www.doesthedogdie.com/">Powered by DoesTheDogDie.com</a>'


def matched(*counts, record=WILLYS, set_by=""):
    return Status(has_tmdb_id=True, match=record.item_id, set_by=set_by, fetched=Fetched(Snapshot(record, counts), AT))


def test_a_matched_film_shows_its_record_tagged_auto_and_its_topics():
    shown = section(matched(TopicCount(153, 3, 1)), VOCABULARY)

    assert shown.state == "matched"
    assert shown.match == DtddMatch(5381, "Willy's Wonderland", 2021, set_by="")
    assert shown.match.url == "https://www.doesthedogdie.com/media/5381"
    assert shown.groups == (TopicGroup("Animals", (TopicRow("dogs dying", 3, 1, 153),)),)
    assert shown.gap == ""
    assert shown.credited


def test_a_match_set_by_someone_names_them():
    assert section(matched(TopicCount(153, 3, 1), set_by="Ada"), VOCABULARY).match.set_by == "Ada"


def test_the_topics_follow_the_vocabularys_groups_with_the_most_yes_votes_first_within_each():
    shown = section(
        matched(TopicCount(153, 3, 1), TopicCount(200, 1, 9), TopicCount(161, 12, 0), TopicCount(300, 2, 2), TopicCount(158, 3, 5)),
        VOCABULARY,
    )

    assert [(group.name, [row.label for row in group.rows]) for group in shown.groups] == [
        ("Violence", ["gun violence"]),
        # Equal yes votes keep the vocabulary's order.
        ("Animals", ["horses dying", "dogs dying", "cats dying"]),
        ("Uncategorized", ["jump scares"]),
    ]
    assert shown.topic_count == 5


def test_a_topic_the_vocabulary_lacks_is_left_out():
    shown = section(matched(TopicCount(153, 3, 1), TopicCount(470, 50, 0)), VOCABULARY)

    assert [row.label for group in shown.groups for row in group.rows] == ["dogs dying"]
    assert shown.topic_count == 1


def test_a_topic_with_votes_but_no_yes_is_left_out_and_one_with_a_single_yes_stays():
    shown = section(matched(TopicCount(153, 0, 110), TopicCount(158, 1, 40), TopicCount(300, 0, 0)), VOCABULARY)

    assert [row.label for group in shown.groups for row in group.rows] == ["cats dying"]
    assert shown.topic_count == 1


def test_a_matched_film_whose_topics_all_have_no_yes_is_still_matched_with_an_empty_list():
    shown = section(matched(TopicCount(153, 0, 110), TopicCount(158, 0, 3)), VOCABULARY)

    assert shown.state == "matched"
    assert shown.groups == ()
    assert shown.topic_count == 0


@pytest.mark.parametrize(
    "status, state, has_match",
    [
        # The id found an empty record, which stays the match.
        (Status(has_tmdb_id=True, match=1210242, fetched=Fetched(Snapshot(Record(1210242, "Werewolf By Night", None, "Movie"), ()), AT)), State.UNCOVERED, True),
        (Status(has_tmdb_id=True, fetched=Fetched(NO_MATCH, AT)), State.UNCOVERED, False),
        (Status(has_tmdb_id=True), State.NOT_FETCHED, False),
        (Status(has_tmdb_id=False), State.NO_MATCH, False),
    ],
)
def test_each_gap_is_named_with_no_topics(status, state, has_match):
    shown = section(status, VOCABULARY)

    assert shown.state == state.replace(" ", "-")
    assert shown.gap == GAPS[state]
    assert shown.groups == ()
    assert (shown.match is not None) == has_match
    # The credit goes with DoesTheDogDie's data: a match shown, or topics (#21).
    assert shown.credited == has_match


def test_not_fetched_says_dtdd_didnt_answer_and_trigger_info_will_load_later():
    assert GAPS[State.NOT_FETCHED] == "DoesTheDogDie didn't answer. Trigger info will load later."


def test_no_gap_reads_as_an_all_clear():
    for gap in GAPS.values():
        assert not re.search(r"\b(clear|safe|none found|no warnings)\b", gap, re.I)


def render(shown, expanded=True):
    film_card = FilmCard(film=THE_SHINING, suggester="Ada", suggester_removed=False, pitch="Watch it late.", notes=(), dtdd=shown)
    return render_to_string("components/film_card.html", {"card": film_card, "expanded": expanded})


def test_the_section_follows_the_notes_and_carries_one_credit_line():
    page = render(section(matched(TopicCount(153, 3, 1), TopicCount(158, 2, 4)), VOCABULARY))

    assert page.index("film-card__notes") < page.index("film-card__phase-bar") < page.index("film-card__dtdd")
    assert page.count(CREDIT) == 1
    assert '<a href="https://www.doesthedogdie.com/media/5381" target="_blank" rel="noopener">' in page
    assert re.search(r"Willy&#x27;s Wonderland \(2021\)&nbsp;↗</a> · <span class=\"dtdd__set-by\">auto</span>", page)
    assert re.search(r'dogs dying</span> — <span class="dtdd__counts">3 yes / 1 no</span>', page)
    assert re.search(r'cats dying</span> — <span class="dtdd__counts">2 yes / 4 no</span>', page)


def test_the_topic_list_is_collapsed_behind_one_control():
    page = render(section(matched(TopicCount(153, 3, 1), TopicCount(158, 2, 4)), VOCABULARY))

    (control,) = re.findall(r"<details[^>]*>\s*<summary[^>]*>(.*?)</summary>", page, re.S)
    assert "2 topics" in control
    assert "<details open" not in page


def test_a_match_set_by_someone_reads_set_by_them():
    page = render(section(matched(TopicCount(153, 3, 1), set_by="Ada"), VOCABULARY))

    assert '<span class="dtdd__set-by">set by Ada</span>' in page


@pytest.mark.parametrize("status", [Status(has_tmdb_id=True), Status(has_tmdb_id=False), Status(has_tmdb_id=True, fetched=Fetched(NO_MATCH, AT))])
def test_a_gap_without_a_match_shows_no_credit_and_no_topic_list(status):
    shown = section(status, VOCABULARY)
    page = render(shown)

    assert shown.gap.replace("'", "&#x27;") in page
    assert CREDIT not in page
    assert "<details" not in page


def test_an_uncovered_match_names_the_gap_under_its_record_with_the_credit():
    empty = Record(1210242, "Werewolf By Night", None, "Movie")
    page = render(section(Status(has_tmdb_id=True, match=empty.item_id, fetched=Fetched(Snapshot(empty, ()), AT)), VOCABULARY))

    assert page.index("Werewolf By Night&nbsp;↗") < page.index("lack of warnings says nothing")
    assert page.count(CREDIT) == 1
    assert "<details" not in page


def test_a_card_without_a_section_renders_none():
    page = render(None)

    assert "film-card__dtdd" not in page
    assert CREDIT not in page


def test_a_record_without_a_year_leaves_the_year_out():
    page = render(section(matched(TopicCount(153, 3, 1), record=replace(WILLYS, release_year=None)), VOCABULARY))

    assert "Willy&#x27;s Wonderland&nbsp;↗</a>" in page
