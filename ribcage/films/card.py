from dataclasses import dataclass

from ribcage.films.film import Film

ELLIPSIS = "…"


@dataclass(frozen=True)
class Note:
    """A voter's own words on a film, by the display name of its author (#21)."""

    author: str
    text: str
    # The viewing voter's own, which an opened card leaves out because their note box holds it (#88).
    yours: bool = False


@dataclass(frozen=True)
class NoteBox:
    """The viewing voter's own note on a film, their pitch on their own suggestion, as the phase bar's box edits it (#21, #88)."""

    text: str
    is_pitch: bool
    # A refusal, gently worded, leaves the text as typed so nothing is lost (#88).
    refusal: str = ""
    saved: bool = False
    # Words typed at the pitch step for a film already in the pool, unsaved, with the focus on them (#93).
    kept: bool = False


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
class TopicRow:
    """One topic on a film, its label and DoesTheDogDie's raw counts: evidence, never a verdict (#20 §4)."""

    label: str
    yes: int
    no: int


@dataclass(frozen=True)
class TopicGroup:
    """A super-category's topics on a film, the most yes votes first (#23, #103)."""

    name: str
    rows: tuple[TopicRow, ...]


@dataclass(frozen=True)
class DtddMatch:
    """The DoesTheDogDie record a film is matched to, and who set it: empty for `auto` (#32, #103)."""

    item_id: int
    name: str
    year: int | None
    set_by: str = ""

    @property
    def url(self):
        return f"https://www.doesthedogdie.com/media/{self.item_id}"


@dataclass(frozen=True)
class DtddSection:
    """The opened card's DoesTheDogDie section, the same for every viewer: the match, the topic list, or the gap named (#20, #21, #103)."""

    # The state's slug, for the section's look: matched, uncovered, not-fetched or no-match.
    state: str
    match: DtddMatch | None = None
    groups: tuple[TopicGroup, ...] = ()
    # The gap in words, empty on a matched film; never an all-clear (#20, #32).
    gap: str = ""
    # Where the list fetches its rows from when it first opens, so no page carries every film's; empty renders them in place (#103).
    topics_at: str = ""

    @property
    def gap_name(self):
        # The glossary's word for the gap, as the Films tab's column names it (#102).
        return self.state.replace("-", " ")

    @property
    def topic_count(self):
        return sum(len(group.rows) for group in self.groups)

    @property
    def credited(self):
        # The credit line whenever the section shows DoesTheDogDie's data: a match or topics (#21).
        return self.match is not None or bool(self.groups)


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
    # The viewing voter's own suggestion, which the pool's Mine filter keeps (#27, #91).
    mine: bool = False
    note_box: NoteBox | None = None
    withdraw: Withdraw | None = None
    runtime_pencil: RuntimePencil | None = None
    # None leaves the section out, as the gallery's plain samples and RUN do (#103, #106).
    dtdd: DtddSection | None = None


def trimmed(text, length):
    """The note as a collapsed card shows it: at most length characters, cut at a word where one is near (#21)."""
    if len(text) <= length:
        return text
    cut = text[:length]
    word_end = cut.rfind(" ")
    if word_end > length * 2 // 3:
        cut = cut[:word_end]
    return cut.rstrip(" ,.;:-–—") + ELLIPSIS
