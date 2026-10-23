from django.conf import settings
from django.db import models, transaction
from django.db.models import Q

from ribcage.films.film import Film, RuntimeSource
from ribcage.identity import display_names


class Approval(models.TextChoices):
    """The admin's standing decision on a suggestion; voters never see it (#27, #28)."""

    UNDECIDED = "undecided", "Undecided"
    APPROVED = "approved", "Approved"
    DROPPED = "dropped", "Dropped"


class SuggestionManager(models.Manager):
    def suggest(self, suggester, film, pitch, runtime=None):
        """The one way a film enters the pool: undecided, with the suggester's pitch as their note (#26).

        A runtime edited at the step is passed beside the film as TMDB gave it, so both are kept (#21, #93).
        """
        with transaction.atomic(using=self._db):
            suggestion = self.create(suggester=suggester, suggester_name=suggester.display_name, **as_suggested(film, runtime))
            suggestion.notes.create(author=suggester, text=pitch)
        return suggestion


class Suggestion(models.Model):
    """A film in the pool, as TMDB or its suggester described it when suggested, and never refreshed (#5, #26)."""

    # Null for a hand-entered film, which no uniqueness holds: two copies are the admin's eye (#26).
    tmdb_id = models.PositiveIntegerField(null=True, unique=True)
    title = models.TextField()
    original_title = models.TextField(null=True)
    year = models.PositiveSmallIntegerField(null=True)
    # One name a line: a JSONField's system check opens the database, which backupcode must not need (#68).
    directors = models.TextField(blank=True, default="")
    certificate = models.TextField(null=True)
    trailer_key = models.TextField(null=True)
    poster_path = models.TextField(null=True)
    imdb_id = models.TextField(null=True)
    # The copy the group will watch, beside TMDB's at fetch time, so the Films tab can flag a difference (#21, #28).
    runtime = models.PositiveSmallIntegerField(null=True)
    tmdb_runtime = models.PositiveSmallIntegerField(null=True)
    approval = models.CharField(max_length=max(map(len, Approval.values)), choices=Approval, default=Approval.UNDECIDED)
    # Blank once the suggester is removed; the kept name still says who suggested it (#26, #28).
    suggester = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="suggestions"
    )
    suggester_name = models.CharField(max_length=display_names.MAX_LENGTH)

    objects = SuggestionManager()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(runtime__gt=0), name="runtime_is_positive"),
            models.CheckConstraint(condition=Q(tmdb_runtime__gt=0), name="tmdb_runtime_is_positive"),
            # SOLVE's one hard constraint needs every film on the ballot to have a length (#26 §8).
            models.CheckConstraint(
                condition=~Q(approval=Approval.APPROVED) | Q(runtime__isnull=False), name="approved_has_a_runtime"
            ),
        ]

    @property
    def runtime_source(self):
        # Derived: TMDB's for as long as the runtime is the one TMDB gave (#21).
        if self.tmdb_runtime is not None and self.runtime == self.tmdb_runtime:
            return RuntimeSource.TMDB
        return RuntimeSource.HAND_ENTERED

    @property
    def film(self):
        return Film(
            tmdb_id=self.tmdb_id,
            title=self.title,
            original_title=self.original_title,
            year=self.year,
            directors=tuple(self.directors.splitlines()),
            certificate=self.certificate,
            trailer_key=self.trailer_key,
            runtime=self.runtime,
            runtime_source=self.runtime_source,
            poster_path=self.poster_path,
            imdb_id=self.imdb_id,
        )

    def __str__(self):
        return self.title


def as_suggested(film, runtime=None):
    """A suggestion's fields for a film; a hand-entered film has no TMDB runtime (#21, #26)."""
    return {
        "tmdb_id": film.tmdb_id,
        "title": film.title,
        "original_title": film.original_title,
        "year": film.year,
        "directors": "\n".join(film.directors),
        "certificate": film.certificate,
        "trailer_key": film.trailer_key,
        "poster_path": film.poster_path,
        "imdb_id": film.imdb_id,
        "runtime": film.runtime if runtime is None else runtime,
        "tmdb_runtime": film.runtime if film.runtime_source is RuntimeSource.TMDB else None,
    }


class Note(models.Model):
    """A voter's own words on a suggestion. The suggester's note is the pitch, not a field of its own (#21, #26)."""

    suggestion = models.ForeignKey(Suggestion, on_delete=models.CASCADE, related_name="notes")
    # Blank once the author is removed, so the pitch outlives them (#26).
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="notes")
    text = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["suggestion", "author"], name="one_note_per_voter_per_suggestion"),
        ]
