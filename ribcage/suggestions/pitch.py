"""The pitch step: a chosen film, the voter's pitch and its runtime, then Add, which puts the film in the pool (#21, #26, #93)."""

from dataclasses import dataclass

from ribcage.films.film import Film
from ribcage.suggestions import notes, runtime
from ribcage.suggestions.models import Suggestion


@dataclass(frozen=True)
class PitchStep:
    """The step as its template reads it: the film, what was typed, and each refusal, said gently beside its box (#93)."""

    film: Film
    # The film signed, for Add to read back without a second fetch (#61).
    signed_film: str = ""
    pitch: str = ""
    # The runtime as last typed, or None while it is still the film's own.
    typed_runtime: str | None = None
    pitch_refusal: str = ""
    runtime_refusal: str = ""

    @property
    def runtime(self):
        if self.typed_runtime is not None:
            return self.typed_runtime
        return "" if self.film.runtime is None else str(self.film.runtime)

    @property
    def runtime_open(self):
        # With no runtime from TMDB, Add needs one typed, so the box is open from the start (the dev, 2026-10-22).
        return self.film.runtime is None or bool(self.runtime_refusal) or self.runtime.strip() != str(self.film.runtime)


class Refused(ValueError):
    def __init__(self, pitch="", runtime=""):
        super().__init__(pitch or runtime)
        self.pitch = pitch
        self.runtime = runtime


class AlreadySuggested(Exception):
    def __init__(self, suggestion):
        super().__init__(suggestion.title)
        self.suggestion = suggestion


def add(voter, film, typed_pitch, typed_runtime):
    """Suggest the film with its pitch and runtime, or refuse with what each box needs; both are required (the dev, 2026-10-22).

    A runtime that differs from the film's is stored beside TMDB's, which stays as fetched, so the card reads by hand (#21, #61).
    """
    # One suggestion per TMDB id; Add runs inside the write lock, so this can't race (#26 §3, #78).
    if film.tmdb_id is not None and (suggested := Suggestion.objects.filter(tmdb_id=film.tmdb_id).first()):
        raise AlreadySuggested(suggested)
    pitch, pitch_refusal = read_pitch(typed_pitch)
    minutes, runtime_refusal = read_runtime(typed_runtime)
    if pitch_refusal or runtime_refusal:
        raise Refused(pitch_refusal, runtime_refusal)
    return Suggestion.objects.suggest(voter, film, pitch, runtime=minutes)


def read_pitch(typed):
    try:
        pitch = notes.note_text(typed)
    except notes.TooLong as refusal:
        return None, notes.too_long(refusal, is_pitch=True)
    return pitch, "" if pitch else notes.PITCH_EMPTY


def read_runtime(typed):
    try:
        return runtime.minutes(typed), ""
    except runtime.Refused as refusal:
        return None, str(refusal)
