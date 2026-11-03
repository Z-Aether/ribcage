"""The film card as the reveal opens it under a row: read-only, with no phase bar, and its DoesTheDogDie section only where the phase keeps any (#29, #158)."""

from dataclasses import replace

from ribcage.ballot import cardbar, reveal
from ribcage.suggestions import pool
from ribcage.triggers import stored, watched


def of(viewer, suggestion, triggers=True):
    """The card for a suggestion on the ballot. `triggers` is False where the phase holds no trigger data, as in RUN (#106, #161).

    It is built for no viewer's note box, so it has no pencil, no withdraw and no marks to toggle, and the viewer's own note shows in the list like anyone's;
    the viewer's matched topics are theirs alone (#111). A match can't be corrected from it, since nothing is written after the reveal (#27, #105).
    """
    section = matched = None
    if triggers:
        ((section, matched),) = stored.sections_and_matches_of([suggestion], watched.ticked_ids(viewer)).values()
        section = replace(pool.listed_from(section, suggestion), correction=None)
    marks = cardbar.marks_by_film([suggestion.pk]).get(suggestion.pk, cardbar.NO_MARKS)
    return pool.film_card(suggestion, pool.notes_in_order().filter(suggestion=suggestion), None, None, section, matched, None, marks)
