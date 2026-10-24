"""The pitch step: a chosen film, the voter's pitch and its runtime, then Add, which puts the film in the pool (#21, #26, #93)."""

import re
from dataclasses import dataclass

from ribcage.films.film import Film, hand_entered
from ribcage.suggestions import notes, runtime
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import fetch


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


@dataclass(frozen=True)
class HandStep(PitchStep):
    """The step for a film TMDB can't find: title and year boxes above the pitch, and a runtime box that starts open (#21, #94)."""

    title: str = ""
    year: str = ""
    title_refusal: str = ""
    year_refusal: str = ""


class Refused(ValueError):
    def __init__(self, pitch="", runtime="", title="", year=""):
        super().__init__(pitch or runtime or title or year)
        self.pitch = pitch
        self.runtime = runtime
        self.title = title
        self.year = year


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
    suggestion = Suggestion.objects.suggest(voter, film, pitch, runtime=minutes)
    # Its trigger data is looked up once the add commits; a film by hand looks nothing up (#32, #102).
    fetch.after_the_add(suggestion)
    return suggestion


TITLE_EMPTY = "A film needs a title. Type what it's called."
# The longest hand-typed title kept, refused whole beyond it like a note over its cap; the field itself has no cap (the dev, 2026-10-23).
TITLE_MAX_LENGTH = 200
YEAR_NOT_A_YEAR = "A year is four digits, like 1994. Type it that way, or leave it empty."


def add_by_hand(voter, typed_title, typed_year, typed_pitch, typed_runtime):
    """Suggest a film typed in by hand: a title, a runtime and a pitch are required, the year is not (#21, #94).

    Nothing is fetched or signed, and no uniqueness holds a hand-entered film: the admin spots duplicates (#26 §3).
    """
    title, title_refusal = read_title(typed_title)
    year, year_refusal = read_year(typed_year)
    if title_refusal or year_refusal:
        # Every box is read, so each refusal shows at once.
        refused = Refused(title=title_refusal, year=year_refusal)
        refused.pitch, refused.runtime = read_pitch(typed_pitch)[1], read_runtime(typed_runtime)[1]
        raise refused
    return add(voter, hand_entered(title, year, None), typed_pitch, typed_runtime)


def read_title(typed):
    title = " ".join(typed.split())
    if len(title) > TITLE_MAX_LENGTH:
        return None, f"That's {len(title):,} characters, and a title holds {TITLE_MAX_LENGTH:,}. Trim it a little."
    return title, "" if title else TITLE_EMPTY


def read_year(typed):
    text = typed.strip()
    if not text:
        return None, ""
    if not re.fullmatch(r"[0-9]{4}", text):
        return None, YEAR_NOT_A_YEAR
    return int(text), ""


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
