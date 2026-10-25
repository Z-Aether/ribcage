"""The trigger data in the database: the vocabulary, replaced whole, and each suggestion's match and snapshot (#26 §7, #32, #102)."""

from django.db import transaction

from ribcage.phase import history
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import section, status
from ribcage.triggers.models import Topic, TriggerData
from ribcage.triggers.vocabulary import UNCATEGORIZED, SuperCategory, Vocabulary
from ribcage.triggers.vocabulary import Topic as VocabularyTopic


def has_vocabulary():
    return Topic.objects.exists()


def replace_vocabulary(vocabulary):
    """The vocabulary replaced whole, unless the phase is RUN, where none is kept: a refresh outlasting the move into RUN writes nothing (#106)."""
    positions = {group: position for position, group in enumerate(vocabulary.super_categories)}
    with transaction.atomic():
        if history.current() is Phase.RUN:
            return
        Topic.objects.all().delete()
        Topic.objects.bulk_create(
            Topic(
                topic_id=topic.topic_id,
                position=position,
                label=topic.label,
                keywords=topic.keywords,
                description=topic.description,
                super_category=topic.super_category.super_category_id,
                super_category_name=None if topic.super_category == UNCATEGORIZED else topic.super_category.name,
                super_category_position=positions.get(topic.super_category),
            )
            for position, topic in enumerate(vocabulary.topics)
        )


def purge():
    """Every snapshot and the vocabulary deleted, as DoesTheDogDie's terms ask on entering RUN; matches, setters and watched lists stay (#26 §7, #106)."""
    with transaction.atomic():
        Topic.objects.all().delete()
        TriggerData.objects.update(snapshot=None)


def stored_vocabulary():
    """The vocabulary in one query, empty when none is stored, as on a fresh database or in RUN (#32)."""
    groups, topics = {}, []
    for row in Topic.objects.order_by("position"):
        group = UNCATEGORIZED if row.super_category_position is None else SuperCategory(row.super_category, row.super_category_name)
        if group != UNCATEGORIZED:
            groups[row.super_category_position] = group
        topics.append(VocabularyTopic(row.topic_id, row.label, row.keywords, row.description, group))
    return Vocabulary(tuple(topics), tuple(groups[position] for position in sorted(groups)))


def store_lookup(suggestion, snapshot, fetched_at):
    """An automatic lookup's answer: its record is the match, tagged `auto`, and the snapshot is replaced whole (#32)."""
    match = None if snapshot.record is None else snapshot.record.item_id
    TriggerData.objects.update_or_create(
        suggestion=suggestion,
        defaults={"match": match, "match_set_by": "", "snapshot": status.as_text(status.Fetched(snapshot, fetched_at))},
    )


def store_refresh(suggestion, asked, snapshot, fetched_at):
    """A refresh's answer for the match it asked about, None for a whole lookup, kept only while that match still stands.

    A correction or a withdraw landing while DoesTheDogDie answered wins, and a corrected match keeps its setter (#104, #105).
    The move into RUN landing meanwhile wins too: no snapshot is stored in RUN (#106).
    """
    with transaction.atomic():
        if history.current() is Phase.RUN:
            return
        if not Suggestion.objects.filter(pk=suggestion.pk).exists():
            return
        if TriggerData.objects.filter(suggestion=suggestion).values_list("match", flat=True).first() != asked:
            return
        if asked is None:
            store_lookup(suggestion, snapshot, fetched_at)
        else:
            TriggerData.objects.filter(suggestion=suggestion).update(snapshot=status.as_text(status.Fetched(snapshot, fetched_at)))


def status_of(suggestion, stored):
    if stored is None:
        return status.Status(has_tmdb_id=suggestion.tmdb_id is not None)
    fetched = None if stored.snapshot is None else status.from_text(stored.snapshot)
    return status.Status(suggestion.tmdb_id is not None, stored.match, stored.match_set_by, fetched)


def statuses_of(suggestions):
    """Each suggestion's status by its id, in one query however large the pool, as the ledger and later surfaces read them (#26 §7)."""
    ids = [suggestion.pk for suggestion in suggestions]
    stored = TriggerData.objects.in_bulk(ids)
    return {suggestion.pk: status_of(suggestion, stored.get(suggestion.pk)) for suggestion in suggestions}


def sections_of(suggestions):
    """Each suggestion's card section by its id, in a query for the trigger data and one for the vocabulary (#103)."""
    vocabulary = stored_vocabulary()
    return {pk: section.section(each, vocabulary) for pk, each in statuses_of(suggestions).items()}


def section_of(suggestion):
    (only,) = sections_of([suggestion]).values()
    return only
