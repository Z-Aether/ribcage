"""The carrying rule: when a film carries a topic, and who is listed under one (#20 §4, #109)."""

from ribcage.triggers.carrying import carriers_by_topic, carries
from ribcage.triggers.dtdd import TopicCount


def test_five_yes_and_no_no_carries(settings):
    assert carries(TopicCount(1, 5, 0))


def test_four_yes_does_not(settings):
    assert not carries(TopicCount(1, 4, 0))


def test_five_yes_and_five_no_does_not_but_five_yes_and_four_no_does(settings):
    assert not carries(TopicCount(1, 5, 5))
    assert carries(TopicCount(1, 5, 4))


def test_the_threshold_is_read_from_the_setting(settings):
    settings.TRIGGER_ICON_THRESHOLD = 2
    assert carries(TopicCount(1, 2, 0)) and not carries(TopicCount(1, 1, 0))
    settings.TRIGGER_ICON_THRESHOLD = 9
    assert not carries(TopicCount(1, 8, 0))


def test_films_are_listed_most_yes_first_then_by_title_and_only_where_they_carry(settings):
    films = [
        ("Zulu", (TopicCount(1, 9, 0),)),
        ("alpha", (TopicCount(1, 9, 0), TopicCount(2, 3, 0))),
        ("Mid", (TopicCount(1, 30, 1),)),
        ("Quiet", (TopicCount(1, 5, 5),)),
        ("Elsewhere", (TopicCount(77, 50, 0),)),
    ]

    assert carriers_by_topic(films, {1, 2}) == {1: ("Mid", "alpha", "Zulu")}
