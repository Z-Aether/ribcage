"""The film card's DoesTheDogDie section, bound from a suggestion's status and the vocabulary, the same for every viewer (#20, #21, #103)."""

from ribcage.films.card import DtddMatch, DtddSection, TopicGroup, TopicRow
from ribcage.triggers.status import State, shown_counts

# Each gap named in words, none of them reading as an all-clear (#20, #32 §2).
GAPS = {
    State.UNCOVERED: "DoesTheDogDie has no trigger data for this film, so the lack of warnings says nothing about it.",
    State.NOT_FETCHED: "DoesTheDogDie didn't answer. Trigger info will load later.",
    State.NO_MATCH: "Added by hand, so it has no DoesTheDogDie match yet.",
}


def section(status, vocabulary):
    fetched = status.fetched
    record = None if fetched is None else fetched.snapshot.record
    match = None if record is None else DtddMatch(record.item_id, record.name, record.release_year, status.set_by)
    groups = () if fetched is None else topic_groups(fetched.snapshot.counts, vocabulary)
    state = status.state
    return DtddSection(state=state.replace(" ", "-"), match=match, groups=groups, gap=GAPS.get(state, ""))


def topic_groups(counts, vocabulary):
    """The counts under the vocabulary's super-categories, in its order, the most yes votes first within each.

    A topic the vocabulary doesn't name is left out until it does, since every move refreshes it first (#62); so is one with no yes vote (#103).
    """
    by_topic = {count.topic_id: count for count in shown_counts(counts, {topic.topic_id for topic in vocabulary.topics})}
    groups = []
    for group, topics in vocabulary.groups:
        # Sorted is stable, so equal yes votes keep DoesTheDogDie's own order.
        named = sorted((topic for topic in topics if topic.topic_id in by_topic), key=lambda topic: -by_topic[topic.topic_id].yes)
        rows = tuple(TopicRow(topic.label, by_topic[topic.topic_id].yes, by_topic[topic.topic_id].no, topic.topic_id) for topic in named)
        if rows:
            groups.append(TopicGroup(group.name, rows))
    return tuple(groups)
