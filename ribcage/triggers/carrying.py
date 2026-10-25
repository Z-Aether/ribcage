"""The one rule for a film carrying a topic, behind the ring, the tray and My warnings' lists of films (#20 §4, #109)."""

from django.conf import settings

from ribcage.triggers.status import shown_counts


def carries(count):
    """At least `TRIGGER_ICON_THRESHOLD` yes votes and more yes votes than no, so one enthusiast marks nothing (#109)."""
    return count.yes >= settings.TRIGGER_ICON_THRESHOLD and count.yes > count.no


def carriers_by_topic(films, topic_ids):
    """The titles of the films carrying each topic, most yes votes first and then by title; `films` pairs a title with its snapshot's counts (#109)."""
    carrying = {}
    for title, counts in films:
        for count in shown_counts(counts, topic_ids):
            if carries(count):
                carrying.setdefault(count.topic_id, []).append((-count.yes, title.casefold(), title))
    return {topic_id: tuple(title for _, _, title in sorted(found)) for topic_id, found in carrying.items()}
