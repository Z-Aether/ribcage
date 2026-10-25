"""The watched list: the topics a voter wants to be told about, private to them (#20 §5, #107)."""

from ribcage.triggers.models import WatchedTopic

# DoesTheDogDie's ids are small positive integers; anything beyond the column's range is no topic (#107).
LARGEST_TOPIC_ID = 2**31 - 1


def is_a_topic_id(topic_id):
    return 0 < topic_id <= LARGEST_TOPIC_ID


def set_ticked(voter, topic_id, ticked):
    """The one write to a watched list, for the page's ticks and the cards' (#107, #114). Idempotent, so a repeated post changes nothing."""
    if ticked:
        WatchedTopic.objects.get_or_create(voter=voter, topic_id=topic_id)
    else:
        WatchedTopic.objects.filter(voter=voter, topic_id=topic_id).delete()


def ticked_ids(voter):
    return set(WatchedTopic.objects.filter(voter=voter).values_list("topic_id", flat=True))
