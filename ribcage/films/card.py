from dataclasses import dataclass

from ribcage.films.film import Film

ELLIPSIS = "…"


@dataclass(frozen=True)
class Note:
    """A voter's own words on a film, by the display name of its author (#21)."""

    author: str
    text: str


@dataclass(frozen=True)
class NoteBox:
    """The viewing voter's own note on a film, their pitch on their own suggestion, as the phase bar's box edits it (#21, #88)."""

    text: str
    is_pitch: bool
    # A refusal, gently worded, leaves the text as typed so nothing is lost (#88).
    refusal: str = ""
    saved: bool = False


@dataclass(frozen=True)
class Withdraw:
    """Withdraw on the viewer's own card, offered only while the film is withdrawable; armed, it says what goes (#27, #89)."""

    goes: str
    armed: bool = False


@dataclass(frozen=True)
class RuntimePencil:
    """The pencil on the runtime line, any voter's in SUGGEST on a withdrawable film; open, the line edits it (#21, #34, #90)."""

    open: bool = False
    # A refused runtime stays as typed beside a gentle refusal, never cut or coerced (#90).
    typed: str | None = None
    refusal: str = ""


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
    # The suggestion a phase bar acts on; the gallery's sample cards have none.
    suggestion_id: int | None = None
    note_box: NoteBox | None = None
    withdraw: Withdraw | None = None
    runtime_pencil: RuntimePencil | None = None


def trimmed(text, length):
    """The note as a collapsed card shows it: at most length characters, cut at a word where one is near (#21)."""
    if len(text) <= length:
        return text
    cut = text[:length]
    word_end = cut.rfind(" ")
    if word_end > length * 2 // 3:
        cut = cut[:word_end]
    return cut.rstrip(" ,.;:-–—") + ELLIPSIS
