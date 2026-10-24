"""The Films tab's ledger: every suggestion a row, newest first, under one of four filters, with the ballot's size and screen time (#28, #95)."""

from dataclasses import dataclass

from django.db.models import Count, Prefetch, Q
from django.urls import reverse

from ribcage.films.card import FilmCard
from ribcage.suggestions import pool
from ribcage.suggestions.models import Approval, Suggestion


@dataclass(frozen=True)
class Filter:
    """One of the tab's filters, read from `?show=`; All shows every approval (#28)."""

    show: str
    label: str
    approval: Approval | None
    nothing_shown: str

    @property
    def address(self):
        # #96 and #97's posts are to reload onto this, so working through a filter stays in it (#95, #96, #97).
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


@dataclass(frozen=True)
class Row:
    """One suggestion's row: its card, which opens under the row, and its approval (#28)."""

    card: FilmCard
    approval: Approval

    @property
    def note_count(self):
        # The pitch counts as a note, as it is the suggester's (#21, #26).
        return len(self.card.notes) + (self.card.pitch is not None)


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
    """The tab's ledger, in a query for the suggestions and one for their notes, however large the pool."""
    suggestions = Suggestion.objects.prefetch_related(Prefetch("notes", queryset=pool.notes_in_order())).order_by("-pk")
    # No viewer: the admin's card has no note box, withdraw or pencil, and shows nothing personal (#28, #95).
    rows = [Row(pool.film_card(suggestion, suggestion.notes.all()), Approval(suggestion.approval)) for suggestion in suggestions]
    return Ledger.of(rows, show)


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
