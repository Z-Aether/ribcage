"""The Films tab's ledger: every suggestion a row, newest first, under one of four filters, with the ballot's size and screen time (#28, #95)."""

from dataclasses import dataclass

from django.db.models import Count, Prefetch, Q
from django.urls import reverse

from ribcage.films.card import FilmCard
from ribcage.suggestions import pool
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.suggestions.runtime import Refused, correct
from ribcage.suggestions.withdrawal import with_holds, withdrawable
from ribcage.triggers import stored
from ribcage.triggers.status import State, Status


@dataclass(frozen=True)
class Filter:
    """One of the tab's filters, read from `?show=`; All shows every approval (#28)."""

    show: str
    label: str
    approval: Approval | None
    nothing_shown: str

    @property
    def address(self):
        # Approve, drop and the runtime box reload onto this, so working through a filter stays in it (#95, #96, #97).
        tab = reverse("console_films")
        return tab if self.approval is None else f"{tab}?show={self.show}"


ALL = Filter("all", "All", None, "Nobody has suggested a film.")
FILTERS = (
    ALL,
    Filter(Approval.UNDECIDED.value, "Undecided", Approval.UNDECIDED, "No film is undecided."),
    Filter(Approval.APPROVED.value, "On the ballot", Approval.APPROVED, "No film is on the ballot."),
    Filter(Approval.DROPPED.value, "Dropped", Approval.DROPPED, "No film is dropped."),
)


def chosen(show):
    """The filter `?show=` names, or All for no value or one that names none."""
    return next((each for each in FILTERS if each.show == show), ALL)


def may_approve(runtime):
    """Whether a film with this runtime may go on the ballot, which SOLVE needs every film's length for (#26 §8, #96)."""
    return runtime is not None


# What a row's two acts make a suggestion; neither returns it to undecided (#61, 2026-10-22).
DECISIONS = (Approval.APPROVED, Approval.DROPPED)


@dataclass(frozen=True)
class Row:
    """One suggestion's row: its card, which opens under the row, and its approval (#28)."""

    card: FilmCard
    approval: Approval
    tmdb_runtime: int | None = None
    dtdd: Status = Status(has_tmdb_id=False)
    # The topics the vocabulary names, as the card lists them (#62).
    named_topics: int = 0

    @property
    def note_count(self):
        # The pitch counts as a note, as it is the suggester's (#21, #26).
        return len(self.card.notes) + (self.card.pitch is not None)

    @property
    def may_approve(self):
        return self.approval != Approval.APPROVED and may_approve(self.card.film.runtime)

    @property
    def may_drop(self):
        return self.approval != Approval.DROPPED

    @property
    def runtime_required(self):
        # Red on the box while Approve is unavailable for want of a runtime, by the same rule (#28, #97).
        return not may_approve(self.card.film.runtime)

    @property
    def tmdb_says(self):
        """TMDB's runtime while the box's differs from it, a cleared one included; the derived source reads the same two (#21, #97)."""
        differs = self.tmdb_runtime is not None and self.card.film.runtime != self.tmdb_runtime
        return self.tmdb_runtime if differs else None

    @property
    def dtdd_status(self):
        """The DoesTheDogDie column: a matched film's topic count, or the gap named; M10 words it finally (#28, #32, #102)."""
        if self.dtdd.state is State.MATCHED:
            return f"{self.named_topics} topic{'' if self.named_topics == 1 else 's'}"
        return str(self.dtdd.state)


@dataclass(frozen=True)
class Tally:
    show: Filter
    count: int
    is_chosen: bool


@dataclass(frozen=True)
class Ledger:
    rows: tuple[Row, ...]
    show: Filter
    filters: tuple[Tally, ...]
    ballot_size: int
    screen_time: int

    @classmethod
    def of(cls, every_row, show):
        """The ledger under a filter, its counts and the ballot's screen time, from every row newest first."""
        approved = [row for row in every_row if row.approval == Approval.APPROVED]
        tallies = tuple(Tally(each, len(shown_by(each, every_row)), each == show) for each in FILTERS)
        # Every approved film has a runtime, which the model's constraint holds (#26 §8).
        return cls(tuple(shown_by(show, every_row)), show, tallies, len(approved), sum(row.card.film.runtime for row in approved))


def shown_by(show, rows):
    return [row for row in rows if show.approval is None or row.approval == show.approval]


def ledger(show):
    """The tab's ledger, in a query each for the suggestions, their notes, their trigger data and the vocabulary, however large the pool."""
    suggestions = list(Suggestion.objects.prefetch_related(Prefetch("notes", queryset=pool.notes_in_order())).order_by("-pk"))
    statuses, named = stored.statuses_of(suggestions), stored.named_topic_ids()
    # No viewer: the admin's card has no note box, withdraw or pencil, and shows nothing personal (#28, #35 §2, #95).
    rows = [
        Row(
            pool.film_card(suggestion, suggestion.notes.all()),
            Approval(suggestion.approval),
            suggestion.tmdb_runtime,
            statuses[suggestion.pk],
            statuses[suggestion.pk].topics_named_by(named),
        )
        for suggestion in suggestions
    ]
    return Ledger.of(rows, show)


def decide(suggestion, expected, to):
    """Approve or drop a suggestion still at the approval the post expected; anything else changes nothing (#28, #96).

    The update names the expected approval too, so a double click, a stale tab or a film withdrawn since find nothing to change.
    """
    if to not in DECISIONS or expected not in Approval.values or expected == to:
        return False
    try:
        matching = Suggestion.objects.filter(pk=suggestion, approval=expected)
        found = matching.first()
    except (TypeError, ValueError):
        return False
    if found is None or (to == Approval.APPROVED and not may_approve(found.runtime)):
        return False
    # Approving also needs a runtime still there, so a clear landing since the read changes nothing (#97).
    if to == Approval.APPROVED:
        matching = matching.filter(runtime__isnull=False)
    return matching.update(approval=to) == 1


# Worded as `runtime.minutes`' lines are, naming no act (#93, #97).
ON_THE_BALLOT = "A film on the ballot needs a runtime. Type its length in minutes, like 144."


@dataclass(frozen=True)
class BoxRefused:
    """A runtime box's refused post: the row it was on, what was typed, kept in the box, and why (#97)."""

    suggestion: int
    typed: str
    says: str


def edit_runtime(suggestion, typed):
    """The admin's runtime edit, in any phase: whole minutes, or blank on a film nothing holds (#28, #97).

    TMDB's runtime stays as fetched, so the source reads by hand. Returns BoxRefused for a refusal; a suggestion
    withdrawn since, or none named, changes nothing.
    """
    try:
        found = with_holds(Suggestion.objects.filter(pk=suggestion)).first()
    except (TypeError, ValueError):
        return None
    if found is None:
        return None
    if not typed.strip():
        # Whatever holds the film refuses the clear, as it does a withdraw, so later holds join it in `withdrawable` (#97, 2026-10-24).
        # The update names the approval too, so an approve landing since the read is refused, as `approved_has_a_runtime` would (#26 §8).
        if withdrawable(found) and Suggestion.objects.filter(pk=found.pk).exclude(approval=Approval.APPROVED).update(runtime=None):
            return None
        return BoxRefused(found.pk, typed, ON_THE_BALLOT)
    try:
        correct(found, typed)
    except Refused as refusal:
        return BoxRefused(found.pk, typed, str(refusal))
    return None


def screen_time_words(minutes):
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return f"{minutes} min"
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


@dataclass(frozen=True)
class Status:
    """The Phase tab's films line (#28, #95)."""

    suggestions: int
    on_the_ballot: int


def status():
    counts = Suggestion.objects.aggregate(suggestions=Count("pk"), on_the_ballot=Count("pk", filter=Q(approval=Approval.APPROVED)))
    return Status(**counts)
