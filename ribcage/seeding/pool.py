"""The seeded pool: films from the recorded corpus, put forward by the seeded voters (#25, #57, #87).

The pitches and notes are written for the seed; none came from the group. The picker's ranking traps,
Evil Dead, Insidious, Good Boy and Willy's Wonderland, are left out, so they can still be suggested.
Sam suggests nothing, so one seeded voter's Mine is empty.
"""

from collections import Counter
from dataclasses import dataclass, replace
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ribcage.films import corpus
from ribcage.identity.models import Voter
from ribcage.phase.order import Phase
from ribcage.seeding.recorded import RecordedDtdd
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.triggers import fetch, status, stored
from ribcage.triggers.client import Client, NotAnswering
from ribcage.triggers.models import TriggerData

CABINET_OF_CURIOSITIES = "Del Toro's Cabinet of Curiosities"
APPROVED, UNDECIDED, DROPPED = Approval.APPROVED, Approval.UNDECIDED, Approval.DROPPED
# Weapons is left not fetched, so the Films tab shows the gap and the next phase move fills it from the recordings (#102, #104).
NOT_FETCHED = 1078605
# The Thing's snapshot is 27 days old, so the Films tab's stale line names it until a move refreshes it (#104).
STALE, STALE_FOR = 1091, timedelta(days=27)
# Exit 8 is matched `auto` to its empty `８番出口` duplicate, which its id lookup also returned, for correcting a match (#57, #105).
WRONGLY_MATCHED, ITS_EMPTY_DUPLICATE = 1408208, 1362774


@dataclass(frozen=True)
class SeededSuggestion:
    # A corpus film's TMDB id, or the hand-entered film's title.
    film: int | str
    suggester: str
    pitch: str
    # Each from APPROVE on; in SUGGEST every suggestion is undecided.
    approval: Approval
    notes: tuple[tuple[str, str], ...] = ()


# Oldest first, so the last is on top of the pool.
SEEDED_POOL = (
    SeededSuggestion(
        1091,
        "Ada",
        "Still the best practical effects ever put on film, and the blood test scene works on a room full of "
        "people like nothing else.",
        APPROVED,
        (("Sam", "In. Lights off for this one."), ("O'Brien", "Didn't we watch it two marathons ago? Happy to again.")),
    ),
    SeededSuggestion(
        530385,
        "Zoë",
        "Broad daylight for two and a half hours, and still the most unsettling thing I've seen. Put it late, "
        "when everyone's a bit raw.",
        APPROVED,
        (
            (
                "Ada",
                "Fair warning: there's one scene about halfway through that the film doesn't cut away from. "
                "You'll know it when it comes.",
            ),
            ("Sam", "I'm in."),
        ),
    ),
    SeededSuggestion(
        1408208,
        "O'Brien",
        "A man stuck walking the same corridor of the Tokyo metro, over and over, looking for what's changed.",
        APPROVED,
        (("Zoë", "Based on the game, but you don't need to have played it."),),
    ),
    SeededSuggestion(
        499537,
        "Anne-Marie",
        "Stop-motion painted straight onto the walls of the room it's set in, so the whole house keeps moving.",
        APPROVED,
        (("Bartholomew Winthrop", "Subtitled, so maybe not the last film of the night."),),
    ),
    SeededSuggestion(
        1079485,
        "Bartholomew Winthrop",
        "It is bad. It knows it is bad. It's the one we'll still be quoting at the next marathon.",
        DROPPED,
        (("Anne-Marie", "Absolutely not. Well. Maybe."),),
    ),
    SeededSuggestion(
        8413,
        "Ada",
        "Hellraiser in space. The ship is the scariest thing in it, and the last twenty minutes are a nightmare.",
        APPROVED,
        (("Bartholomew Winthrop", "The gravity drive room alone."),),
    ),
    SeededSuggestion(
        CABINET_OF_CURIOSITIES,
        "Zoë",
        "Just the one episode, The Autopsy. Forty-seven minutes on my copy, so it fits the gap after dinner.",
        UNDECIDED,
        (("Sam", "Great shout, that one's grim."),),
    ),
    SeededSuggestion(
        420634,
        "Bartholomew Winthrop",
        "Art the Clown. Not a word out of him the whole film, and you won't be able to look away.",
        APPROVED,
        (("Anne-Marie", "Very, very gory. I'll probably be making tea for this one."),),
    ),
    SeededSuggestion(
        354912,
        "Anne-Marie",
        "Not horror, I know, but it's the Day of the Dead and it will make you cry. Something gentle between "
        "the heavy ones.",
        DROPPED,
        (("O'Brien", "Love it, but on a horror night? Up for it if the others are."), ("Ada", "Yes please.")),
    ),
    SeededSuggestion(
        694,
        "O'Brien",
        "Kubrick at his coldest. Heeere's Johnny.",
        APPROVED,
        (("Zoë", "The hedge maze on a big screen is worth the whole evening."),),
    ),
    SeededSuggestion(
        16296,
        "Bartholomew Winthrop",
        "Cotton candy cocoons and popcorn guns. Peak eighties, and the theme song will be stuck in your head "
        "for a week.",
        APPROVED,
        (("Sam", "Good one for early on, before anyone's tired."),),
    ),
    SeededSuggestion(
        284303,
        "Zoë",
        "Twin boys, and a mother who comes home from surgery with her face in bandages and isn't quite their "
        "mother any more. Quiet and nasty.",
        APPROVED,
        (("Ada", "The original, not the remake, right?"),),
    ),
    SeededSuggestion(
        60366,
        "Ada",
        "A turkey with a knife. Seventy minutes long, and every one of them is a terrible decision.",
        DROPPED,
    ),
    SeededSuggestion(
        1063879,
        "O'Brien",
        "Spiders in a Paris tower block. If you're scared of spiders, this is the worst film ever made; if "
        "you're not, it's one of the best.",
        APPROVED,
        (("Anne-Marie", "I am scared of spiders. I will be in the kitchen."),),
    ),
    SeededSuggestion(
        894205,
        "Anne-Marie",
        "Black and white, under an hour, a monster hunt in a creepy mansion. A good short one between features.",
        APPROVED,
        (("Sam", "Marvel, but you don't need to have seen any of the others."),),
    ),
    SeededSuggestion(
        744857,
        "Zoë",
        "Argentinian possession horror that breaks every rule you think it has set. The bleakest thing on the "
        "list, by a mile.",
        APPROVED,
        (
            ("O'Brien", "Saw this at a festival and couldn't sleep. Strongly recommend, strongly warn."),
            ("Bartholomew Winthrop", "Is there a dog in it? Asking for a friend."),
        ),
    ),
    SeededSuggestion(
        1212763,
        "Bartholomew Winthrop",
        "The new Evil Dead, by the director of Infested. I haven't seen it yet, which is half the fun.",
        UNDECIDED,
    ),
    SeededSuggestion(
        431,
        "Ada",
        "Six strangers wake up in a maze of cube rooms full of traps. Cheap, tight, and argued about for hours "
        "afterwards.",
        APPROVED,
        (("Zoë", "The maths bits are the best bits."),),
    ),
    SeededSuggestion(
        1005776,
        "Anne-Marie",
        "Five shorts and a frame story, so if one is dull the next is ten minutes away.",
        APPROVED,
        (("Sam", "The punk one is the best opening of the series."), ("Ada", "Loud, though. Earlier on, maybe?")),
    ),
    SeededSuggestion(
        1078605,
        "O'Brien",
        "A whole class of kids runs out of their houses at 2:17 one night and vanishes. I saw it at the cinema "
        "and would love to see it again with you lot.",
        UNDECIDED,
        (("Zoë", "Yes! Nobody spoil anything."),),
    ),
)


def seed_the_pool(phase):
    films = recorded_films()
    voters = {voter.display_name: voter for voter in Voter.objects.all()}
    for seeded in SEEDED_POOL:
        suggestion = Suggestion.objects.suggest(voters[seeded.suggester], films[seeded.film], seeded.pitch)
        for author, text in seeded.notes:
            suggestion.notes.create(author=voters[author], text=text)
        if phase is not Phase.SUGGEST:
            suggestion.approval = seeded.approval
            suggestion.save(update_fields=["approval"])


def recorded_films():
    # Read from fixtures/films/, so seeding never goes online (#57).
    return {
        recorded.film.tmdb_id if recorded.film.tmdb_id is not None else recorded.film.title: recorded.film
        for recorded in corpus.read_corpus()
    }


def seed_the_trigger_data():
    """Each seeded TMDB film's lookup, answered from the recordings by the rule a suggestion's is, and the state each lands in (#102).

    Returns the recordings, so the seed can say when they are missing, as in a fresh clone.
    """
    # Read at call time, so a test can point the seed at a corpus of its own.
    recordings = RecordedDtdd(corpus.CORPUS_DIRECTORY, corpus.VOCABULARY_DIRECTORY)
    client = Client(settings.DTDD_API_KEY, recordings)
    for suggestion in Suggestion.objects.exclude(tmdb_id=NOT_FETCHED).order_by("pk"):
        fetch.look_up(suggestion, client)
    match_wrongly(WRONGLY_MATCHED, ITS_EMPTY_DUPLICATE, client)
    age_the_snapshot(STALE, STALE_FOR)
    return recordings


def match_wrongly(tmdb_id, item_id, client):
    """The film matched `auto` to the record given, as a confidently wrong lookup would leave it; unrecorded, it stays as looked up."""
    try:
        snapshot = client.record(item_id).value
    except NotAnswering:
        return
    for suggestion in Suggestion.objects.filter(tmdb_id=tmdb_id):
        stored.store_lookup(suggestion, snapshot, timezone.now())


def age_the_snapshot(tmdb_id, by):
    for row in TriggerData.objects.filter(suggestion__tmdb_id=tmdb_id, snapshot__isnull=False):
        fetched = status.from_text(row.snapshot)
        row.snapshot = status.as_text(replace(fetched, fetched_at=fetched.fetched_at - by))
        row.save(update_fields=["snapshot"])


def trigger_states():
    """How many seeded films are in each state, for the seed's output."""
    suggestions = list(Suggestion.objects.all())
    return Counter(each.state for each in stored.statuses_of(suggestions).values())
