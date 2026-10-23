"""What the gallery shows: real films from the recorded corpus, with voters and notes written for the gallery (#58).

None of the names or notes here came from the group. They exist to put each real case on screen:
a posterless film, a long title, a differing original title, a hand-entered runtime, many notes
against only a pitch, and a removed suggester.
"""

from dataclasses import dataclass, replace
from functools import cache

from ribcage.films import corpus
from ribcage.films.card import FilmCard, Note, NoteBox, Withdraw
from ribcage.suggestions.views import PITCH_REQUIRED
from ribcage.suggestions.withdrawal import what_goes

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
def films():
    by_key = {}
    for recorded in corpus.read_corpus():
        film = recorded.film
        by_key[film.tmdb_id if film.tmdb_id is not None else film.title] = film
    return by_key


def film(key):
    return films()[key]


def cards():
    return (
        FilmCard(
            film=film(MIDSOMMAR),
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
            suggester="Ivo",
            suggester_removed=True,
            pitch="Just the one episode, The Autopsy. 47 minutes of my copy, so it fits in the gap after dinner.",
            notes=(),
        ),
        FilmCard(
            film=film(VHS_99),
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
            suggester="Bex",
            suggester_removed=False,
            pitch="A man is stuck walking one corridor of the Tokyo metro, over and over.",
            notes=(Note("Hanna", "Based on the game! You do not need to have played it."),),
        ),
    )


def own(sample, armed=False):
    """The sample as its suggester sees it: their pitch in the box, and Withdraw on the card (#88, #89)."""
    withdraw = Withdraw(goes=what_goes(len(sample.notes)), armed=armed)
    return replace(sample, note_box=NoteBox(text=sample.pitch, is_pitch=True), withdraw=withdraw)


def phase_bars():
    """Each pool phase's bar on an opened card, with no suggestion, so a save here only reloads onto the phase page (#88).

    A withdraw confirmed here names no suggestion, so it takes nothing, and the sample card only leaves until a reload (#89).
    """
    wolf_house, vhs_99, exit_8 = cards()[2], cards()[4], cards()[5]
    return (
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
            replace(wolf_house, note_box=NoteBox(text=wolf_house.notes[0].text, is_pitch=False, saved=True)),
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
        "score_scale": SCORE_SCALE,
        "tiles": tiles(),
        "poster_row": poster_row(),
        "evening": evening(),
        "evening_minutes": 425,
        "evening_now": 245,
    }
