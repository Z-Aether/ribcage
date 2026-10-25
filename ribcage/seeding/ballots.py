"""The seeded ballots, from VOTE on: Ada has scored most of the ballot, Zoë part of it with a veto, and Bartholomew Winthrop none, as the voter who never votes (#50, #119, #120).

Each score is by the film's TMDB id. A film a voter leaves out is left in their Unsorted tray, and PICK and RUN keep the same scores (#63).
"""

from ribcage.ballot.models import BallotRecord
from ribcage.identity.models import Voter
from ribcage.suggestions.models import Suggestion

THE_THING, MIDSOMMAR, EXIT_8, MARIA, EVENT_HORIZON, TERRIFIER, THE_SHINING, COTTON_CANDY = 1091, 530385, 1408208, 499537, 8413, 420634, 694, 16296
GOODNIGHT_MOMMY, INFESTED, SHORT_MONSTER, WOLF_HOUSE, CUBE, VHS_99 = 284303, 1063879, 894205, 744857, 431, 1005776

# Ada leaves The Thing, Event Horizon, Infested, Cube and Werewolf by Night in her tray: the first four ring for her, the last does not.
SEEDED_SCORES = {
    "Ada": {MIDSOMMAR: 3, EXIT_8: 2, MARIA: 1, TERRIFIER: -1, THE_SHINING: 3, COTTON_CANDY: 0, GOODNIGHT_MOMMY: 2, WOLF_HOUSE: -1, VHS_99: 2},
    "Zoë": {THE_THING: 3, CUBE: 2, EXIT_8: 1, INFESTED: -1, COTTON_CANDY: 0, MARIA: 2},
    "Anne-Marie": {THE_THING: 1, THE_SHINING: 2},
    "Sam": {COTTON_CANDY: 3},
}

# Each veto is (film, reason or None): Terrifier is vetoed by two voters, for the ribbon's two initials, one of them without a reason (#120).
SEEDED_VETOES = {
    "Zoë": {TERRIFIER: "I won't sit through that one, and I'd rather say so now."},
    "Anne-Marie": {TERRIFIER: None},
    "Sam": {WOLF_HOUSE: "Too close to a nightmare I had."},
}


def seed_the_ballots():
    voters = {voter.display_name: voter for voter in Voter.objects.all()}
    suggestions = {suggestion.tmdb_id: suggestion for suggestion in Suggestion.objects.exclude(tmdb_id=None)}
    BallotRecord.objects.bulk_create(
        BallotRecord(voter=voters[name], suggestion=suggestions[tmdb_id], score=score) for name, scores in SEEDED_SCORES.items() for tmdb_id, score in scores.items()
    )
    BallotRecord.objects.bulk_create(
        BallotRecord(voter=voters[name], suggestion=suggestions[tmdb_id], vetoed=True, veto_reason=reason) for name, vetoes in SEEDED_VETOES.items() for tmdb_id, reason in vetoes.items()
    )
