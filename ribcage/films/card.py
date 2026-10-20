from dataclasses import dataclass

from ribcage.films.film import Film

ELLIPSIS = "…"


@dataclass(frozen=True)
class Note:
    """A voter's own words on a film, by the display name of its author (#21)."""

    author: str
    text: str


@dataclass(frozen=True)
class FilmCard:
    """Everything the film card shows, as plain data, so a model binds to it without touching the template (#21, #58)."""

    film: Film
    suggester: str
    # A removed voter's suggestion and pitch stay, marked removed (#8, #28).
    suggester_removed: bool
    pitch: str | None
    # Every other voter's note, in the order the card shows them after the pitch.
    notes: tuple[Note, ...]


def trimmed(text, length):
    """The note as a collapsed card shows it: at most length characters, cut at a word where one is near (#21)."""
    if len(text) <= length:
        return text
    cut = text[:length]
    word_end = cut.rfind(" ")
    if word_end > length * 2 // 3:
        cut = cut[:word_end]
    return cut.rstrip(" ,.;:-–—") + ELLIPSIS
