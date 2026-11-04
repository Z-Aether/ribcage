"""Keeping and discarding a proposal: the only writes of the shortlist, and the one read of it (#17, #169)."""

from dataclasses import dataclass

from django.db import transaction

from ribcage.ballot.board import candidates
from ribcage.shortlist.models import KeptFilm, KeptProposal


@dataclass(frozen=True)
class Kept:
    pk: int
    provenance: str
    films: tuple


def load():
    """The shortlist in the order kept, in two queries however long it is."""
    return [Kept(each.pk, each.provenance, tuple(sorted(film.suggestion_id for film in each.films.all()))) for each in KeptProposal.objects.order_by("pk").prefetch_related("films")]


def keep(films, provenance):
    """Store the film set as it was proposed, under `provenance`, the basis's words as plain text; the proposal, or None where nothing was written.

    Nothing is written for an empty set, a film that is no longer a candidate (only choosing a dropped film afresh is blocked, #26 §5),
    or a film set already on the shortlist.
    """
    with transaction.atomic():
        ids = set(films)
        if not ids or ids != set(candidates().filter(pk__in=ids).values_list("pk", flat=True)):
            return None
        if any(frozenset(each.films) == ids for each in load()):
            return None
        proposal = KeptProposal.objects.create(provenance=provenance)
        KeptFilm.objects.bulk_create(KeptFilm(proposal=proposal, suggestion_id=pk) for pk in sorted(ids))
        return proposal


def discard(pk):
    """Take a proposal off the shortlist; a stale post for one already gone changes nothing."""
    KeptProposal.objects.filter(pk=pk).delete()
