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
    # The author vetoes the film, on a surface that shows vetoes; with no text it is a bare line naming them (#128).
    vetoed: bool = False


@dataclass(frozen=True)
class NoteBox:
    """The viewing voter's own note on a film, their pitch on their own suggestion, as the phase bar's box edits it (#21, #88)."""

    text: str
    is_pitch: bool
    # A refusal, gently worded, leaves the text as typed so nothing is lost (#88).
    refusal: str = ""
    # Words typed at the pitch step for a film already in the pool, unsaved, with the focus on them (#93).
    kept: bool = False
    # What is saved when the box holds other words, typed and refused or kept from the pitch step; None where the box holds what is saved (#132).
    was: str | None = None

    @property
    def saved_text(self):
        return self.text if self.was is None else self.was

    @property
    def unsaved(self):
        """Whether the box is drawn holding words not yet saved, so *Save* starts enabled (#132)."""
        return self.kept or bool(self.refusal)


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
    # The vocabulary's id, which a watch toggle posts in its body; 0 for a sample's row (#114).
    topic_id: int = 0


@dataclass(frozen=True)
class TopicGroup:
    """A super-category's topics on a film, the most yes votes first (#23, #103)."""

    name: str
    rows: tuple[TopicRow, ...]


def record_url(item_id):
    # The item page a voter pastes, and the one a match links to (#103, #105).
    return f"https://www.doesthedogdie.com/media/{item_id}"


@dataclass(frozen=True)
class DtddMatch:
    """The DoesTheDogDie record a film is matched to, and who set it: empty for `auto` (#32, #103)."""

    item_id: int
    name: str
    year: int | None
    set_by: str = ""

    @property
    def url(self):
        return record_url(self.item_id)


@dataclass(frozen=True)
class MatchPreview:
    """The record a pasted link names, as fetched, shown before Use this match saves it, signed for the film it was fetched for (#105)."""

    item_id: int
    name: str
    year: int | None
    item_type: str
    topic_count: int
    signed: str

    @property
    def url(self):
        return record_url(self.item_id)


@dataclass(frozen=True)
class MatchCorrection:
    """The paste-a-link control on the match line, one for every voter and the admin, each posting to their own route (#32 §5, #105)."""

    # The route the box asks and Use this match posts to.
    at: str
    # A refused link stays as pasted beside a gentle refusal (#105).
    typed: str = ""
    refusal: str = ""
    preview: MatchPreview | None = None

    @property
    def search(self):
        # DoesTheDogDie's search box is the home page's first field; no address fills it in, as its search answers by script alone (#105).
        return "https://www.doesthedogdie.com/"


@dataclass(frozen=True)
class Watch:
    """The viewer's *watch* toggles on a topic list: where one posts, the card it swaps, and the topics already on their list (#114)."""

    # Empty leaves the toggles inert, as the gallery's are.
    at: str
    suggestion_id: int | None
    ticked: frozenset[int]


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
    # None offers no control, as the gallery's plain samples and RUN do (#105, #106).
    correction: MatchCorrection | None = None
    # None offers no toggles: the admin's card, and a voter with *I don't care* on (#110, #114).
    watch: Watch | None = None
    # The topic list drawn open with its rows in place, as a watch toggle's answer is, rather than left to fetch (#114).
    opened: bool = False

    @property
    def gap_name(self):
        # The glossary's word for the gap, as the Films tab's column names it (#102).
        return self.state.replace("-", " ")

    @property
    def topic_count(self):
        return sum(len(group.rows) for group in self.groups)

    @property
    def credited(self):
        # The credit line whenever the section shows DoesTheDogDie's data: a match or topics (#21); a preview carries its own (#105).
        return self.match is not None or bool(self.groups)


@dataclass(frozen=True)
class Matched:
    """The viewer's matched topics on a film, evaluated when the page is drawn, and whether the film rings for them (#20 §3–§4, #111)."""

    rows: tuple[TopicRow, ...]
    # How many matched rows the one carrying rule counts as carried (#109); the ring's count pill shows it (#117).
    strong: int

    @property
    def ring(self):
        # The trigger icon: some matched topic is carried.
        return self.strong > 0


@dataclass(frozen=True)
class VoteBar:
    """What VOTE's phase bar shows for the viewer on one film: their own say, which is theirs alone, and the other voters' seen it (#10, #35 §4, #122).

    The vetoes are in the card's notes, not the bar (#128)."""

    # The scale's buttons as (score, key, sign, name), top pick first.
    scale: tuple[tuple[int, str, str, str], ...]
    score: int | None = None
    vetoed: bool = False
    # The voter's note on the film, which is their veto's reason, or their pitch on their own suggestion (#128).
    note: str = ""
    is_pitch: bool = False
    seen_it: bool = False
    seen_by: tuple[str, ...] = ()
    # A refusal of the box's save, kept as the note box keeps its refusal; a saved reason answers the tile, so says nothing (#120, #132).
    said: str = ""
    refused: bool = False
    # What is saved when the box holds other words, typed and refused; None where the box holds what is saved (#132).
    was: str | None = None

    @property
    def saved_text(self):
        return self.note if self.was is None else self.was
    # The gallery's bar posts nowhere, so its buttons only look.
    inert: bool = False


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
    # The viewing voter's matched topics; None for the admin, a voter with nothing ticked and a film matching nothing (#35 §2, #111).
    matched: Matched | None = None
    # VOTE's bar data; None in every other phase (#122).
    vote: VoteBar | None = None
    # The suggester vetoes the film, on a surface that shows vetoes (#128).
    pitch_vetoed: bool = False

    @property
    def pitch_yours(self):
        # The viewer's own pitch is left out of an opened card only where a box holds it: the note box, or VOTE's reason box while they veto (#88, #122, #128).
        return self.mine and (self.note_box is not None or (self.vote is not None and self.vote.vetoed))


def trimmed(text, length):
    """The note as a collapsed card shows it: at most length characters, cut at a word where one is near (#21)."""
    if len(text) <= length:
        return text
    cut = text[:length]
    word_end = cut.rfind(" ")
    if word_end > length * 2 // 3:
        cut = cut[:word_end]
    return cut.rstrip(" ,.;:-–—") + ELLIPSIS
