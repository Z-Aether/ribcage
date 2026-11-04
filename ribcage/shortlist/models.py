from django.db import models


class KeptProposal(models.Model):
    """A proposal the admin kept: its film set and where it came from, and nothing scored; `keeping` is the one way it is kept and discarded (#17, #26 §5, #169).

    The order kept is the key's. Provenance is a plain copy in words, display names and titles included, never a link to a voter or a film,
    so *without Iván* stays readable after Iván is removed; it explains and never scores.
    """

    provenance = models.CharField(max_length=2000)


class KeptFilm(models.Model):
    """One film of a kept proposal."""

    proposal = models.ForeignKey(KeptProposal, on_delete=models.CASCADE, related_name="films")
    # PROTECT: a hold `withdrawal.withdrawable` misses makes the delete fail instead of cascading (#66, 2026-10-23).
    suggestion = models.ForeignKey("suggestions.Suggestion", on_delete=models.PROTECT, related_name="kept_in")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["proposal", "suggestion"], name="a_film_is_kept_once_per_proposal")]
