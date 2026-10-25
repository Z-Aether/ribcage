"""The seeded watched lists, chosen by the label DoesTheDogDie gives each topic (#107)."""

from django.conf import settings

from ribcage.identity.models import Voter
from ribcage.triggers import watched
from ribcage.triggers.client import Client, NotAnswering

# Ada's ring on most seeded films; Zoë's rings on one film once; Sam ticks nothing, so the nag shows for him (#107, #110).
SEEDED_WATCHED_LISTS = {
    "Ada": ["blood or gore", "jump scares", "animal abuse"],
    "Zoë": ["aliens"],
}


def seed_the_watched_lists(recordings):
    """Each list ticked from the recorded vocabulary, not the stored one, which RUN's seed leaves empty; a fresh clone has no recording, so its lists are empty."""
    try:
        topics = Client(settings.DTDD_API_KEY, recordings).vocabulary().value.topics
    except NotAnswering:
        return
    ids = {topic.label: topic.topic_id for topic in topics}
    for display_name, labels in SEEDED_WATCHED_LISTS.items():
        voter = Voter.objects.get(display_name=display_name)
        for label in labels:
            if label in ids:
                watched.set_ticked(voter, ids[label], True)
