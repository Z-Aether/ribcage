"""The seeded ballots, from VOTE on: Ada has scored most of the ballot, Zoë part of it with a veto, and Bartholomew Winthrop none, as the voter who never votes (#50, #119, #120).

Each score is by the film's TMDB id. A film a voter leaves out is left in their Unsorted tray, and PICK and RUN keep the same scores (#63).
"""

from ribcage.ballot.models import BallotRecord, DoneMarker
from ribcage.identity.models import Voter
from ribcage.suggestions.models import Note, Suggestion

THE_THING, MIDSOMMAR, EXIT_8, WOLF_HOUSE, EVENT_HORIZON, TERRIFIER, THE_SHINING, KILLER_KLOWNS = 1091, 530385, 1408208, 499537, 8413, 420634, 694, 16296
GOODNIGHT_MOMMY, INFESTED, WEREWOLF_BY_NIGHT, WHEN_EVIL_LURKS, CUBE, VHS_99 = 284303, 1063879, 894205, 744857, 431, 1005776

# Ada leaves The Thing, Event Horizon, Infested, Cube and Werewolf by Night in her tray: the first four ring for her, the last does not.
SEEDED_SCORES = {
    "Ada": {MIDSOMMAR: 3, EXIT_8: 2, WOLF_HOUSE: 1, TERRIFIER: -1, THE_SHINING: 3, KILLER_KLOWNS: 0, GOODNIGHT_MOMMY: 2, WHEN_EVIL_LURKS: -1, VHS_99: 2},
    "Zoë": {THE_THING: 3, CUBE: 2, EXIT_8: 1, INFESTED: -1, KILLER_KLOWNS: 0, WOLF_HOUSE: 2},
    # Exit 8 is on the seeded evening, so the floor is above 0 and removing a box can drop it (#147).
    "Anne-Marie": {THE_THING: 1, THE_SHINING: 2, EXIT_8: 2},
    "Sam": {KILLER_KLOWNS: 3},
    # Only 0 and -1: no film to stand for them, so the floor set shows *nothing representable* beside Bartholomew Winthrop's *no ballot* (#146).
    "O'Brien": {KILLER_KLOWNS: 0, TERRIFIER: -1},
}

# Each veto is (film, the note it is written as or None): Terrifier is vetoed by two voters, for the ribbon's two initials.
# Zoë wrote hers as the reason, Anne-Marie's reason is the note she wrote in SUGGEST, and Sam has no note, so his is a bare line (#120, #128).
SEEDED_VETOES = {
    "Zoë": {TERRIFIER: "I won't sit through that one, and I'd rather say so now."},
    "Anne-Marie": {TERRIFIER: None},
    "Sam": {WHEN_EVIL_LURKS: None},
}

# Seen it, by film: Ada's Midsommar is seen and scored, Zoë's Terrifier seen and vetoed, Ada's Cube seen and left in her tray, Zoë's The Shining seen with no other say (#121).
SEEDED_SEEN = {"Ada": (MIDSOMMAR, CUBE), "Zoë": (TERRIFIER, THE_SHINING)}


# Anne-Marie and O'Brien are done; Bartholomew Winthrop never votes and is not (#123).
SEEDED_DONE = ("Anne-Marie", "O'Brien")


def seed_the_ballots():
    voters = {voter.display_name: voter for voter in Voter.objects.all()}
    suggestions = {suggestion.tmdb_id: suggestion for suggestion in Suggestion.objects.exclude(tmdb_id=None)}
    BallotRecord.objects.bulk_create(
        BallotRecord(voter=voters[name], suggestion=suggestions[tmdb_id], score=score) for name, scores in SEEDED_SCORES.items() for tmdb_id, score in scores.items()
    )
    BallotRecord.objects.bulk_create(
        BallotRecord(voter=voters[name], suggestion=suggestions[tmdb_id], vetoed=True) for name, vetoes in SEEDED_VETOES.items() for tmdb_id in vetoes
    )
    Note.objects.bulk_create(
        Note(suggestion=suggestions[tmdb_id], author=voters[name], text=text) for name, vetoes in SEEDED_VETOES.items() for tmdb_id, text in vetoes.items() if text
    )
    for name, films in SEEDED_SEEN.items():
        for tmdb_id in films:
            record, _ = BallotRecord.objects.get_or_create(voter=voters[name], suggestion=suggestions[tmdb_id])
            record.seen_it = True
            record.save(update_fields=["seen_it"])
    DoneMarker.objects.bulk_create(DoneMarker(voter=voters[name]) for name in SEEDED_DONE)
