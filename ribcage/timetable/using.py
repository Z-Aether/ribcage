"""*Use this slate*: a film set laid on the timetable in place of every box, previewed or saved by the same call (#12, #36, #171).

The films go in slate order on the stored votes, back to back from the anchor. A dropped film is laid as the film it is, carrying its mark:
only choosing a dropped film afresh is blocked (#26 §5). The set arrives as suggestion ids, so a later ticket arms the same call for a batch proposal's films (#172).
"""

from django.db import transaction

from ribcage.shortlist import keeping
from ribcage.suggestions.models import Suggestion
from ribcage.timetable import engine, offering, setting, track
from ribcage.timetable.models import Box


def kept_films(proposal_id):
    """The suggestion ids of the kept proposal with this key, or None where it is gone or the key is nonsense."""
    try:
        wanted = int(proposal_id)
    except (TypeError, ValueError):
        return None
    return next((each.films for each in keeping.load() if each.pk == wanted), None)


def lay(films, save):
    """The track's boxes after the film set replaces every box, stored when `save`; None with no anchor or an empty set, so the caller reloads the tab.

    Recomputed from what is stored now, so a save lays what the preview showed unless a vote moved between the two (#36).
    """
    with transaction.atomic():
        if not films or setting.read().anchor is None:
            return None
        ordered = offering.in_slate_order(Suggestion.objects.filter(pk__in=films))
        laid = engine.lay_back_to_back((each.pk, each.runtime) for each in ordered)
        if save:
            Box.objects.all().delete()
            Box.objects.bulk_create(Box(suggestion=film, start=each.start) for film, each in zip(ordered, laid, strict=True))
            return track.stored_boxes()
        return track.film_boxes([(f"new-{film.pk}", each.start, film) for film, each in zip(ordered, laid, strict=True)])
