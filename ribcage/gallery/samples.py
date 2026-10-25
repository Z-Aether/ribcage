"""What the gallery shows: real films from the recorded corpus, with voters and notes written for the gallery (#58).

None of the names or notes here came from the group. They exist to put each real case on screen:
a posterless film, a long title, a differing original title, a hand-entered runtime, many notes
against only a pitch, and a removed suggester. Every card but Cass's carries the runtime pencil, as SUGGEST
shows it on a film nothing holds; hers also stands for APPROVE's bar and the admin's ledger, which show none (#90).
Each card's DoesTheDogDie section is written for the gallery too, its topics and counts made up in DoesTheDogDie's
own words and grouping, since its recordings stay out of the repo (#40, #103).
"""

from dataclasses import dataclass, replace
from functools import cache

from ribcage.films import corpus
from ribcage.films.card import (
    DtddMatch,
    DtddSection,
    FilmCard,
    Matched,
    MatchCorrection,
    MatchPreview,
    Note,
    NoteBox,
    RuntimePencil,
    TopicGroup,
    TopicRow,
    Watch,
    Withdraw,
)
from ribcage.films.picker import Picker, PickerTile
from ribcage.suggestions.notes import PITCH_REQUIRED
from ribcage.suggestions.runtime import NOT_WHOLE_MINUTES
from ribcage.suggestions.withdrawal import what_goes
from ribcage.triggers import correction
from ribcage.triggers.carrying import carries
from ribcage.triggers.section import GAPS
from ribcage.triggers.status import State

MIDSOMMAR = 530385
POOH_2 = 1079485
WOLF_HOUSE = 499537
VHS_99 = 1005776
EXIT_8 = 1408208
THE_THING = 1091
THE_SHINING = 694
CARRIE_2013 = 133805
TERRIFIER = 420634
THE_EXORCIST = 9552
EVENT_HORIZON = 8413
CUBE = 431
INFESTED = 1063879
CABINET_OF_CURIOSITIES = "Del Toro's Cabinet of Curiosities"

SCORE_SCALE = (
    ("+3", "Top pick", "top-pick"),
    ("+2", "Keen", "keen"),
    ("+1", "Happy", "happy"),
    ("0", "Don't mind", "dont-mind"),
    ("−1", "Rather not", "rather-not"),
)


@dataclass(frozen=True)
class Tile:
    """A poster tile as the ballot will frame it, to show the state colours together (M6 builds the real one)."""

    film: object
    caption: str
    trigger_icon: bool = False
    seen_it: bool = False
    vetoed_by: str = ""


@dataclass(frozen=True)
class EveningBox:
    """A box on the sample RUN evening, in minutes from the anchor (M7 and M8 build the real one)."""

    label: str
    start: str
    end: str
    offset: int
    length: int
    film: object = None
    past: bool = False
    now: bool = False
    minutes_left: int = 0


@cache
def searches():
    return {recorded.entry.written_title: recorded.search_results for recorded in corpus.read_corpus()}


def picker():
    """The picker for "evil dead", with Evil Dead Burn already in the pool and Insidious (2008)'s title card in the last slot (#92).

    The mix is the gallery's own: a real search never puts the two together. Choosing a tile here does nothing.
    """
    evil_dead = searches()["Evil Dead"]
    insidious_2008 = next(result for result in searches()["Insidious"] if result.year == 2008)
    tiles = (PickerTile(evil_dead[0], suggested_by="Ash"), *map(PickerTile, evil_dead[1:4]), PickerTile(insidious_2008))
    return Picker(searched=True, tiles=tiles, choosable=False)


@cache
def films():
    by_key = {}
    for recorded in corpus.read_corpus():
        film = recorded.film
        by_key[key_of(film)] = film
    return by_key


def film(key):
    return films()[key]


def key_of(film):
    return film.tmdb_id if film.tmdb_id is not None else film.title


TOPIC_IDS = {}


def topic_id(label):
    """A sample topic's stand-in id, the same wherever its label shows, so a row and the matched block agree on what is watched (#114)."""
    return TOPIC_IDS.setdefault(label, len(TOPIC_IDS) + 1)


def topics(*groups):
    return tuple(TopicGroup(name, tuple(TopicRow(label, yes, no, topic_id(label)) for label, yes, no in rows)) for name, rows in groups)


def matched_section(item_id, name, year, groups, set_by=""):
    return DtddSection("matched", DtddMatch(item_id, name, year, set_by), topics(*groups))


def gap(state, match=None):
    return DtddSection(state.replace(" ", "-"), match, gap=GAPS[state])


MIDSOMMAR_DTDD = matched_section(
    20449,
    "Midsommar",
    2019,
    (
        ("Animals", (("animals (besides dog/cat/horse) dying", 14, 2), ("dogs dying", 1, 31))),
        ("Bodily Harm", (("blood or gore", 38, 1), ("body horror", 22, 3), ("self harming", 6, 9))),
        ("Death, Grief & Loss", (("family dies", 30, 0), ("major character dies", 27, 1))),
        ("Phobias & Sensory", (("jump scares", 2, 25), ("flashing lights or images", 1, 7))),
        ("Sexual Content/Assault", (("sexual content", 26, 2), ("druggings", 24, 0))),
        ("Violence", (("people dying by suicide", 29, 1), ("torture", 9, 4))),
    ),
)
SECTIONS = {
    MIDSOMMAR: MIDSOMMAR_DTDD,
    POOH_2: gap(State.NOT_FETCHED),
    WOLF_HOUSE: matched_section(
        126608,
        "The Wolf House",
        2018,
        (("Children & Babies", (("kids dying", 8, 1),)), ("Phobias & Sensory", (("claustrophobic scenes", 6, 0),))),
        set_by="Dani",
    ),
    CABINET_OF_CURIOSITIES: gap(State.NO_MATCH),
    VHS_99: matched_section(918990, "V/H/S/99", 2022, (("Bodily Harm", (("blood or gore", 3, 1), ("vomiting", 4, 2))),)),
    # Matched to an empty record, so uncovered with its match shown, as the seed's Exit 8 is (#57).
    EXIT_8: gap(State.UNCOVERED, DtddMatch(1362774, "８番出口", 2025)),
}


def dtdd_states():
    """The section in each of its four states, each on an opened card with the match line's control (#103, #105)."""
    by_key = {key_of(sample.film): sample for sample in cards()}
    return (
        ("Matched, its topics behind one control", by_key[MIDSOMMAR]),
        ("Uncovered, on the empty record it was matched to", by_key[EXIT_8]),
        ("Not fetched", by_key[POOH_2]),
        ("No match, added by hand", by_key[CABINET_OF_CURIOSITIES]),
    )


def watching():
    """Midsommar's topic list opened, as a watch toggle's answer draws it: watched rows read so, the rest offer to watch (#114)."""
    midsommar = next(sample for sample in cards() if key_of(sample.film) == MIDSOMMAR)
    return (("the full topic list open, blood or gore and jump scares watched", replace(midsommar, dtdd=replace(midsommar.dtdd, opened=True))),)


def corrections():
    """A correction's preview, and a refused link kept in the box, on Exit 8's wrong match (#105)."""
    exit_8 = next(sample for sample in cards() if key_of(sample.film) == EXIT_8)
    control = exit_8.dtdd.correction
    # Signed for no film, so Use this match here is refused, as the gallery's controls lead nowhere.
    found = MatchPreview(1558416, "Exit 8", 2025, "Movie", 282, signed="")
    refused = replace(control, typed="https://www.imdb.com/title/tt32252772/", refusal=correction.NOT_A_LINK)
    return (
        ("the preview of a pasted link, before Use this match", replace(exit_8, dtdd=replace(exit_8.dtdd, correction=replace(control, preview=found)))),
        ("a refused link, kept in the box", replace(exit_8, dtdd=replace(exit_8.dtdd, correction=refused))),
    )


# Inert: with no route the control's box and buttons fire no request (#105).
INERT = MatchCorrection(at="")
# The sample viewer's list, which the matched blocks above are built from, and whose toggles fire no request either (#114).
WATCHING = Watch(at="", suggestion_id=None, ticked=frozenset(topic_id(label) for label in ("blood or gore", "jump scares", "kids dying", "vomiting")))


def matched_of(section):
    """The viewer's matched block on a section, by the app's own rule: the watched rows, most yes votes first, and a ring when one is carried (#111)."""
    rows = sorted((row for group in section.groups for row in group.rows if row.topic_id in WATCHING.ticked), key=lambda row: -row.yes)
    return Matched(tuple(rows), ring=any(carries(row) for row in rows)) if rows else None


def cards():
    # Midsommar and The Wolf House ring, V/H/S/99's thin matches are listed without a ring (#111).
    return tuple(
        replace(sample, dtdd=replace(SECTIONS[key_of(sample.film)], correction=INERT, watch=WATCHING), matched=matched_of(SECTIONS[key_of(sample.film)]))
        for sample in plain_cards()
    )


def plain_cards():
    return (
        FilmCard(
            film=film(MIDSOMMAR),
            runtime_pencil=RuntimePencil(),
            suggester="Hanna",
            suggester_removed=False,
            pitch=(
                "Broad daylight for two and a half hours and it is still the most frightening thing I have seen. "
                "Watch it late, after the loud ones, when everyone is a bit raw. Bring tissues, honestly."
            ),
            notes=(
                Note("Ash", "Seen it twice. The second time is worse, because you know where it is going."),
                Note(
                    "Bex",
                    "Fair warning for anyone squeamish: there is one scene about halfway through that you will "
                    "want to look away from, and the film does not cut away. You will know it when it comes.",
                ),
                Note("Dani", "I'm in."),
                Note(
                    "Eli",
                    "It's 147 minutes as listed. If we take the director's cut instead, it runs nearer three hours, "
                    "so somebody correct the runtime if that's the copy we bring.",
                ),
                Note("Fen", "The flower dress alone earns its place on the ballot."),
            ),
        ),
        FilmCard(
            film=film(POOH_2),
            runtime_pencil=RuntimePencil(),
            suggester="Gus",
            suggester_removed=False,
            pitch="It is bad. It knows it is bad. It is the one we will still be quoting at the next marathon.",
            notes=(),
        ),
        FilmCard(
            film=film(WOLF_HOUSE),
            suggester="Cass",
            suggester_removed=False,
            pitch=(
                "Stop-motion painted straight onto the walls of the room it's set in, so the whole house keeps "
                "moving. Short, strange and like nothing else on the list."
            ),
            notes=(Note("Dani", "Subtitled, so not the last film of the night."),),
        ),
        FilmCard(
            film=film(CABINET_OF_CURIOSITIES),
            runtime_pencil=RuntimePencil(),
            suggester="Ivo",
            suggester_removed=True,
            pitch="Just the one episode, The Autopsy. 47 minutes of my copy, so it fits in the gap after dinner.",
            notes=(),
        ),
        FilmCard(
            film=film(VHS_99),
            runtime_pencil=RuntimePencil(),
            suggester="Eli",
            suggester_removed=False,
            pitch="Five shorts and a frame story, so if one is dull the next is ten minutes away.",
            notes=(
                Note("Fen", "The punk one is the best opening of the series."),
                Note("Ash", "Bit loud for late on. Earlier in the evening, maybe?"),
            ),
        ),
        FilmCard(
            film=film(EXIT_8),
            runtime_pencil=RuntimePencil(),
            suggester="Bex",
            suggester_removed=False,
            pitch="A man is stuck walking one corridor of the Tokyo metro, over and over.",
            notes=(Note("Hanna", "Based on the game! You do not need to have played it."),),
        ),
    )


def own(sample, armed=False):
    """The sample as its suggester sees it: their pitch in the box, and Withdraw on the card (#88, #89)."""
    withdraw = Withdraw(goes=what_goes(len(sample.notes)), armed=armed)
    return replace(sample, mine=True, note_box=NoteBox(text=sample.pitch, is_pitch=True), withdraw=withdraw)


def yours(sample, index):
    """The sample's note at that index as the viewer's own, which the opened card leaves to their box (#88)."""
    notes = tuple(replace(note, yours=True) if i == index else note for i, note in enumerate(sample.notes))
    return replace(sample, notes=notes)


def phase_bars():
    """Each pool phase's bar on an opened card, with no suggestion, so a save here only reloads onto the phase page (#88).

    A withdraw confirmed here names no suggestion, so it takes nothing, and the sample card only leaves until a reload (#89).
    The runtime pencil names none either, so opening or saving it here reloads onto the phase page (#90).
    """
    midsommar, wolf_house, vhs_99, exit_8 = cards()[0], cards()[2], cards()[4], cards()[5]
    return (
        (
            "SUGGEST's runtime pencil, open on Hanna's suggestion, as Dani typed the director's cut in hours",
            replace(
                yours(midsommar, 2),
                note_box=NoteBox(text=midsommar.notes[2].text, is_pitch=False),
                runtime_pencil=RuntimePencil(open=True, typed="2h 51", refusal=NOT_WHOLE_MINUTES),
            ),
            "components/suggest_bar.html",
        ),
        (
            "SUGGEST's phase bar, on Bex's own suggestion, after she saved her pitch empty",
            replace(own(exit_8), note_box=NoteBox(text=exit_8.pitch, is_pitch=True, refusal=PITCH_REQUIRED)),
            "components/suggest_bar.html",
        ),
        (
            "SUGGEST's phase bar, on Eli's own suggestion, with Withdraw armed",
            own(vhs_99, armed=True),
            "components/suggest_bar.html",
        ),
        (
            "APPROVE's phase bar, on Cass's suggestion, as Dani just saved her note",
            replace(yours(wolf_house, 0), note_box=NoteBox(text=wolf_house.notes[0].text, is_pitch=False, saved=True)),
            "components/approve_bar.html",
        ),
    )


def tiles():
    return (
        Tile(film(THE_SHINING), "A topic you watch for", trigger_icon=True),
        Tile(film(CARRIE_2013), "Seen it", seen_it=True),
        Tile(film(TERRIFIER), "Vetoed by others", vetoed_by="BH"),
        Tile(film(THE_EXORCIST), "Nothing to say"),
        Tile(film(CABINET_OF_CURIOSITIES), "All three, on a title card", trigger_icon=True, seen_it=True, vetoed_by="G"),
    )


def poster_row():
    return [film(key) for key in (THE_THING, EVENT_HORIZON, CABINET_OF_CURIOSITIES, INFESTED, CUBE, POOH_2, EXIT_8)]


def evening():
    return (
        EveningBox("The Thing", "18:00", "19:49", 0, 109, film=film(THE_THING), past=True),
        EveningBox("Dinner", "20:00", "20:45", 120, 45, past=True),
        EveningBox("Midsommar", "20:50", "23:17", 170, 147, film=film(MIDSOMMAR), now=True, minutes_left=72),
        EveningBox("Exit 8", "23:30", "01:05", 330, 95, film=film(EXIT_8)),
    )


def gallery():
    return {
        "cards": cards(),
        "phase_bars": phase_bars(),
        "dtdd_states": dtdd_states(),
        "watching": watching(),
        "corrections": corrections(),
        "score_scale": SCORE_SCALE,
        "tiles": tiles(),
        "picker": picker(),
        "picker_outage": Picker(searched=True, outage=True, choosable=False),
        "poster_row": poster_row(),
        "evening": evening(),
        "evening_minutes": 425,
        "evening_now": 245,
    }
