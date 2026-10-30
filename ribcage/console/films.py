"""The Films tab's ledger: every suggestion a row, newest first, under one of four filters, with the ballot's size and screen time (#28, #95)."""

from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.urls import reverse
from django.utils import timezone

from ribcage.ballot import cardbar, done
from ribcage.films.card import FilmCard, Marks
from ribcage.identity.models import Voter
from ribcage.phase.history import current, vote_has_opened
from ribcage.phase.order import Phase
from ribcage.suggestions import pool
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.suggestions.runtime import Refused, correct
from ribcage.suggestions.withdrawal import with_holds, withdrawable
from ribcage.triggers import stored
from ribcage.triggers.section import section
from ribcage.triggers.status import STALE_AFTER, State, Status


@dataclass(frozen=True)
class Filter:
    """One of the tab's filters, read from `?show=`; All shows every approval (#28)."""

    show: str
    label: str
    approval: Approval | None
    nothing_shown: str

    @property
    def arm_address(self):
        # Approve's arm is a plain GET at the filter's address plus the row; a film id follows (#124).
        return f"{self.address}{'&' if self.approval else '?'}arm="

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
    # The topics the card lists: named, with a yes vote (#62, #103).
    shown_topics: int = 0
    # Who vetoes the film and who has seen it, counted over every voter's records whatever its approval (#153).
    marks: Marks = Marks()

    @property
    def note_count(self):
        # The pitch counts as a note, as it is the suggester's (#21, #26); a vetoer's bare line is no note (#153).
        return sum(1 for note in self.card.notes if note.text) + (self.card.pitch is not None)

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
            return f"{self.shown_topics} topic{'' if self.shown_topics == 1 else 's'}"
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
    # Empty while no film's trigger data is old or missing (#104).
    stale_line: str = ""
    # False in RUN, which shows no trigger data: no column, no stale line, no section and no credit (#106).
    shows_dtdd: bool = True

    @classmethod
    def of(cls, every_row, show, now, shows_dtdd=True):
        """The ledger under a filter, its counts, the ballot's screen time and the stale line, from every row newest first."""
        approved = [row for row in every_row if row.approval == Approval.APPROVED]
        tallies = tuple(Tally(each, len(shown_by(each, every_row)), each == show) for each in FILTERS)
        # Every approved film has a runtime, which the model's constraint holds (#26 §8).
        screen_time = sum(row.card.film.runtime for row in approved)
        return cls(tuple(shown_by(show, every_row)), show, tallies, len(approved), screen_time, stale_line(every_row, now) if shows_dtdd else "", shows_dtdd)


def stale_line(rows, now):
    """The films whose trigger data is over 25 days old or not yet fetched, named whatever the filter; M10 words it finally (#28, #32 §1, #104)."""
    stale = [row.card.film.title for row in rows if row.dtdd.is_stale(now)]
    unfetched = [row.card.film.title for row in rows if row.dtdd.state is State.NOT_FETCHED]
    if not stale and not unfetched:
        return ""
    parts = ([f"over {STALE_AFTER.days} days old for {listed(stale)}"] if stale else []) + ([f"not yet fetched for {listed(unfetched)}"] if unfetched else [])
    they = "They refresh" if len(stale) + len(unfetched) > 1 else "It refreshes"
    return f"Trigger data is {', and '.join(parts)}. {they} on the next phase move."


def listed(titles):
    return titles[0] if len(titles) == 1 else f"{', '.join(titles[:-1])} and {titles[-1]}"


def shown_by(show, rows):
    return [row for row in rows if show.approval is None or row.approval == show.approval]


# The card's topic list fetches its rows from the console's own route, behind the admin's wall (#103), and its match is corrected at another (#105).
LISTED_FROM, CORRECTED_AT = "console_films_dtdd", "console_films_dtdd_match"


def ledger(show):
    """The tab's ledger, in a query each for the suggestions, their notes, their trigger data and the vocabulary, however large the pool."""
    suggestions = list(Suggestion.objects.prefetch_related(Prefetch("notes", queryset=pool.notes_in_order())).order_by("-pk"))
    marks = cardbar.marks_by_film()
    if current() == Phase.RUN:
        return run_ledger(suggestions, show, marks)
    statuses, vocabulary = stored.statuses_of(suggestions), stored.stored_vocabulary()
    named = {topic.topic_id for topic in vocabulary.topics}
    # No viewer: the admin's card has no note box, withdraw or pencil, and shows nothing personal (#28, #35 §2, #95).
    # Its DoesTheDogDie section is the one every voter sees (#35 §2, #103).
    rows = [
        Row(
            pool.film_card(suggestion, suggestion.notes.all(), dtdd=listed_section(section(statuses[suggestion.pk], vocabulary), suggestion), marks=marks.get(suggestion.pk)),
            Approval(suggestion.approval),
            suggestion.tmdb_runtime,
            statuses[suggestion.pk],
            statuses[suggestion.pk].topics_shown_by(named),
            marks.get(suggestion.pk, cardbar.NO_MARKS),
        )
        for suggestion in suggestions
    ]
    return Ledger.of(rows, show, timezone.now())


def run_ledger(suggestions, show, marks):
    """RUN's ledger: the purge left no trigger data to show, so a card has no section and the rows no status (#106)."""
    rows = [
        Row(pool.film_card(suggestion, suggestion.notes.all(), marks=marks.get(suggestion.pk)), Approval(suggestion.approval), suggestion.tmdb_runtime, marks=marks.get(suggestion.pk, cardbar.NO_MARKS))
        for suggestion in suggestions
    ]
    return Ledger.of(rows, show, timezone.now(), shows_dtdd=False)


def listed_section(dtdd, suggestion):
    return pool.listed_from(dtdd, suggestion, LISTED_FROM, CORRECTED_AT)


def the_card(suggestion):
    """One suggestion's card as it opens under its row, to swap its section in place after a correction (#105)."""
    marks = cardbar.marks_by_film([suggestion.pk]).get(suggestion.pk)
    return pool.film_card(suggestion, pool.notes_in_order().filter(suggestion=suggestion), dtdd=listed_section(stored.section_of(suggestion), suggestion), marks=marks)


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
    # Growing the ballot once VOTE has opened clears every done marker, in the same write (#124).
    with transaction.atomic():
        if matching.update(approval=to) != 1:
            return False
        if to == Approval.APPROVED and vote_has_opened():
            done.clear_all()
    return True


@dataclass(frozen=True)
class Cost:
    """What approving a film costs once VOTE has opened, read before the confirm (#28, #124)."""

    done: int
    voters: int
    vote_closed: bool

    @property
    def says(self):
        return f"Adds it to every voter's ballot and clears every done marker: {self.done} of {self.voters} → 0 of {self.voters}."

    @property
    def closed_line(self):
        return "VOTE is closed, so nobody can score the film unless VOTE is reopened." if self.vote_closed else ""


@dataclass(frozen=True)
class Done:
    done: int
    voters: int


def done_so_far():
    """Who has pressed done, for the console's lines; None before VOTE has ever opened, as the Roster's columns are (#28, #124)."""
    return Done(done.count(), Voter.objects.count()) if vote_has_opened() else None


def cost_of_approving():
    """The cost an approval asks about first, or None before VOTE has ever opened, when it is instant (#96, #124)."""
    if not vote_has_opened():
        return None
    return Cost(done.count(), Voter.objects.count(), current() in (Phase.PICK, Phase.RUN))


# Worded as `runtime.minutes` lines are, naming no act and no hold, so every hold fits it (#93, #97, #118).
HELD = "A film in use needs a runtime. Type its length in minutes, like 144."


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
        return BoxRefused(found.pk, typed, HELD)
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
