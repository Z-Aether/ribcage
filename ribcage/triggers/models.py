from django.conf import settings
from django.db import models

from ribcage.identity import display_names
from ribcage.suggestions.models import Suggestion


class TriggerData(models.Model):
    """A suggestion's DoesTheDogDie match and snapshot, deleted with it (#26 §7, #32, #102)."""

    suggestion = models.OneToOneField(Suggestion, on_delete=models.CASCADE, primary_key=True, related_name="trigger_data")
    # The DoesTheDogDie item id, or none; it survives the RUN purge, so the refresh after RUN is one call a film (#32 §1, #106).
    match = models.PositiveIntegerField(null=True)
    # Empty for `auto`; else a kept copy of the setter's name, as `suggester_name` is (#105).
    match_set_by = models.CharField(max_length=display_names.MAX_LENGTH, blank=True, default="")
    # `status.as_text`'s JSON, read and written whole; null until DoesTheDogDie answers (#32 §2, #68).
    snapshot = models.TextField(null=True)


class Topic(models.Model):
    """One topic of DoesTheDogDie's vocabulary, which is replaced whole and never edited (#23, #102)."""

    topic_id = models.PositiveIntegerField(primary_key=True)
    # DoesTheDogDie's own order, for topics and for their super-categories alike (#23).
    position = models.PositiveIntegerField(unique=True)
    # Its minimalName (#23).
    label = models.TextField()
    keywords = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    # All three null for Uncategorized.
    super_category = models.IntegerField(null=True)
    super_category_name = models.TextField(null=True)
    super_category_position = models.PositiveIntegerField(null=True)


class WatchedTopic(models.Model):
    """One topic on a voter's watched list, deleted with the voter (#20 §5, #107)."""

    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watched_topics")
    # A plain DoesTheDogDie topic id, not a link to `Topic`: the RUN purge neither deletes it nor is blocked by it, and a retired topic never matches (#107).
    topic_id = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["voter", "topic_id"], name="one_row_per_watched_topic")]
