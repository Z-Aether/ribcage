"""A viewer's matched topics on a film, and the ring, pure over a watched list and a snapshot's counts (#20 §3–§4, #111)."""

from ribcage.films.card import Matched, TopicRow
from ribcage.triggers.carrying import carries
from ribcage.triggers.status import shown_counts


def matched(counts, vocabulary, ticked):
    """The topics on the snapshot that are also on the watched list, most yes votes first, each with its raw counts, or None when none is.

    A matched topic is a shown one (#103): a ticked topic with no yes vote or outside the vocabulary isn't listed, which is a design question (#111).
    The ring is the carrying rule over those same counts; the rows have no threshold (#20 §4).
    """
    if not ticked:
        return None
    labels = {topic.topic_id: topic.label for topic in vocabulary.topics}
    found = sorted((count for count in shown_counts(counts, set(labels)) if count.topic_id in ticked), key=lambda count: -count.yes)
    if not found:
        return None
    return Matched(rows=tuple(TopicRow(labels[count.topic_id], count.yes, count.no, count.topic_id) for count in found), strong=sum(carries(count) for count in found))
