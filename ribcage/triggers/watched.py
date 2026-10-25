"""The watched list: the topics a voter wants to be told about, private to them (#20 §5, #107)."""

from django.db import transaction

from ribcage.triggers.models import DoesNotCare, WatchedTopic

# DoesTheDogDie's ids are small positive integers; anything beyond the column's range is no topic (#107).
LARGEST_TOPIC_ID = 2**31 - 1


def is_a_topic_id(topic_id):
    return 0 < topic_id <= LARGEST_TOPIC_ID


def set_ticked(voter, topic_id, ticked):
    """The one write of a single tick, for the page's ticks and the cards' (#107, #114); `stop_caring` is the one way the list is cleared. Idempotent, so a repeated post changes nothing.

    Returns whether it was applied: a tick is refused while *I don't care* is on, which means nothing is ticked (#110).
    """
    if ticked:
        if does_not_care(voter):
            return False
        WatchedTopic.objects.get_or_create(voter=voter, topic_id=topic_id)
    else:
        WatchedTopic.objects.filter(voter=voter, topic_id=topic_id).delete()
    return True


def ticked_ids(voter):
    return set(WatchedTopic.objects.filter(voter=voter).values_list("topic_id", flat=True))


def does_not_care(voter):
    """Whether the voter has pressed *I don't care*, which greys their list out. #114's card toggles ask this before they are offered (#110)."""
    return DoesNotCare.objects.filter(voter=voter).exists()


def stop_caring(voter):
    """*I don't care* on: the ticks go with it, as nothing is ticked while it is on. Idempotent (#110)."""
    with transaction.atomic():
        WatchedTopic.objects.filter(voter=voter).delete()
        DoesNotCare.objects.get_or_create(voter=voter)


def care_again(voter):
    """*I don't care* off: the list comes back, empty. Idempotent (#110)."""
    DoesNotCare.objects.filter(voter=voter).delete()


def has_decided(voter):
    """A voter who has ticked something or pressed *I don't care* is no longer nudged by the nag bar (#110)."""
    return WatchedTopic.objects.filter(voter=voter).exists() or does_not_care(voter)
