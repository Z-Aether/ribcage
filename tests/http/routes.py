"""Every route sorted into public, voter or admin by the marks on its view, for the tests that hold each kind to its rules (#76)."""

import re
from typing import NamedTuple

import pytest
from django.urls import URLResolver, get_resolver

PUBLIC = "public"
VOTER = "voter"
ADMIN = "admin"

# Public routes that answer POST alone: each log out, outside the walls so a stale tab's lands on a login (#70, #76).
PUBLIC_POSTS = {"logout", "admin_logout"}

# Routes that act or fetch a piece rather than show: a plain GET redirects, which their own tests hold, so the page sweeps leave them out (#89, #90, #92, #93, #103, #105, #107, #110, #119, #133).
ACTS = {"withdraw", "runtime", "find", "suggest", "dtdd_topics", "console_films_dtdd", "dtdd_match", "console_films_dtdd_match", "warnings_tick", "warnings_dont_care", "dtdd_watch", "ballot_place", "ballot_seen", "ballot_card", "ballot_done", "console_pick_anchor", "console_pick_budget", "console_pick_add", "console_pick_remove", "console_pick_break", "console_pick_box", "console_pick_preview", "console_pick_move", "console_pick_resize", "console_pick_mode", "console_pick_place", "console_pick_arrange"}

class Fragment(NamedTuple):
    """One htmx answer that swaps a card, its section or a part of one in, which test_dtdd_credit.py sweeps for DoesTheDogDie's data (#112).

    `parameters` are format strings over `{film}` (a suggestion's id), `{snapshot}` (a signed one) and `{topic}`, sent as the query of a GET and the body of a POST.
    A `part` swaps inside a region of DoesTheDogDie's data that the page already carries and credits, so it holds no region of its own.
    """

    route: str
    viewer: str
    method: str
    parameters: dict
    part: bool = False


# Every answer that shows DoesTheDogDie's data: a voter or admin route that is no page, or whose plain GET redirects or answers 405, is listed here or in NO_DTDD_DATA, which test_dtdd_credit.py holds (#112).
# The links name records the test's fake DoesTheDogDie answers (9001) or has none of (9002).
FRAGMENTS = [
    # First, while the voter has no note: a drop into the Veto band answers the film's card only where they have none, so it carries the section (#120, #150).
    Fragment("ballot_place", VOTER, "POST", {"suggestion": "{film}", "to": "veto"}),
    # In VOTE a saved note answers the film's tile, and a refused one the open card, which carries the section (#132, #150).
    Fragment("note", VOTER, "POST", {"suggestion": "{film}", "text": "A note."}),
    Fragment("note", VOTER, "POST", {"suggestion": "{film}", "text": "x" * 5001}),
    # A refused runtime answers the open card, with the runtime's refusal beside its box (#133).
    Fragment("note", VOTER, "POST", {"suggestion": "{film}", "text": "A note.", "runtime": "abc"}),
    Fragment("withdraw", VOTER, "POST", {"suggestion": "{film}"}),
    # Before the watch toggles below, which untick the list the row's matched topics come from.
    # The opened card carries the section; its own writes answer the card moved or the checkbox (#122).
    Fragment("ballot_card", VOTER, "GET", {"suggestion": "{film}"}),
    Fragment("ballot_place", VOTER, "POST", {"suggestion": "{film}", "to": "2", "card": "1"}),
    Fragment("dtdd_topics", VOTER, "GET", {"suggestion": "{film}"}, part=True),
    Fragment("dtdd_match", VOTER, "GET", {"suggestion": "{film}", "cancel": ""}),
    Fragment("dtdd_match", VOTER, "GET", {"suggestion": "{film}", "link": "https://www.doesthedogdie.com/media/9001"}),
    Fragment("dtdd_match", VOTER, "GET", {"suggestion": "{film}", "link": "https://www.doesthedogdie.com/media/9002"}),
    Fragment("console_films_dtdd", ADMIN, "GET", {"suggestion": "{film}"}, part=True),
    Fragment("console_films_dtdd_match", ADMIN, "GET", {"suggestion": "{film}", "cancel": ""}),
    Fragment("console_films_dtdd_match", ADMIN, "GET", {"suggestion": "{film}", "link": "https://www.doesthedogdie.com/media/9001"}),
    Fragment("console_films_dtdd_match", ADMIN, "GET", {"suggestion": "{film}", "link": "https://www.doesthedogdie.com/media/9002"}),
    # A refusal renders the whole Films tab, ledger and cards among it (#97).
    Fragment("console_films_runtime", ADMIN, "POST", {"suggestion": "{film}", "runtime": "abc"}),
    Fragment("warnings_tick", VOTER, "POST", {"topic": "{topic}", "ticked": "1"}, part=True),
    # The card's toggle answers the whole section, open, with its own credit (#114).
    Fragment("dtdd_watch", VOTER, "POST", {"suggestion": "{film}", "topic": "{topic}", "ticked": "1"}),
    Fragment("dtdd_watch", VOTER, "POST", {"suggestion": "{film}", "topic": "{topic}", "ticked": "0"}),
    Fragment("warnings_dont_care", VOTER, "GET", {}, part=True),
    # Last, since each saves a match.
    Fragment("dtdd_match", VOTER, "POST", {"suggestion": "{film}", "snapshot": "{snapshot}"}),
    Fragment("console_films_dtdd_match", ADMIN, "POST", {"suggestion": "{film}", "snapshot": "{snapshot}"}),
]

# Voter and admin routes that are no swept page and whose answers hold none of DoesTheDogDie's data, whatever is stored (#112).
NO_DTDD_DATA = {
    "runtime", "find", "suggest",  # the runtime pencil's read, the picker and the suggest act; the runtime is saved by the note's post (#133)
    "gallery",  # dev-only, answering 404 outside DEBUG
    "console", "console_phase_move", "console_films_approval",  # redirects, whatever they act on
    "ballot_done",  # the header's done block: names and ticks, no film (#123)
    "ballot_seen",  # a tile, or the card's checkbox, never matched topics (#121, #122)
    "console_pick_anchor", "console_pick_budget",  # the Pick header's saves: a redirect, or the tab with a refusal (#135)
    "console_pick_add", "console_pick_remove", "console_pick_break",  # the timetable's hand edits: a redirect to the tab (#137)
    "console_pick_preview", "console_pick_move", "console_pick_resize", "console_pick_place", "console_pick_arrange",  # a drag's preview, the track alone, and its saves, redirects to the tab (#139, #143)
    "console_pick_mode",  # the ripple mode's save: a redirect to the tab (#140)
    "console_pick_runtime",  # a film box's runtime save: a redirect to the tab, or the tab with a refusal (#142)
    "console_pick_box",  # a redirect to the tab, or the tab with a refusal (#137, #138)
    "console_roster_remove", "console_roster_reset", "console_backup_upload",  # the roster's and backup page's acts
}

# A value each built-in converter accepts, so a route with one is requested at an address it answers (#76).
SAMPLES = {"int": "1", "str": "x", "slug": "x", "path": "x", "uuid": "00000000-0000-0000-0000-000000000000"}
PARAMETER = re.compile(r"<(?:(?P<converter>[^>:]+):)?(?P<parameter>[^>]+)>")


def route_templates(patterns=None, prefix="/"):
    for entry in get_resolver().url_patterns if patterns is None else patterns:
        if isinstance(entry, URLResolver):
            yield from route_templates(entry.url_patterns, prefix + str(entry.pattern))
        else:
            yield prefix + str(entry.pattern), entry


def address(template):
    return PARAMETER.sub(lambda parameter: SAMPLES[parameter["converter"] or "str"], template)


def routes():
    for template, entry in route_templates():
        yield address(template), entry


def kind(entry):
    """PUBLIC, VOTER or ADMIN, or None for a view marked as both voter-walled and admin-walled."""
    # login_not_required takes a view outside the voter wall (#16); admin_required also puts it behind the admin's.
    outside_the_voter_wall = getattr(entry.callback, "login_required", True) is False
    if getattr(entry.callback, "admin_required", False):
        return ADMIN if outside_the_voter_wall else None
    return PUBLIC if outside_the_voter_wall else VOTER


def routes_of(route_kind):
    return [(path, entry) for path, entry in routes() if kind(entry) == route_kind]


def pages_of(route_kind):
    # A page with an id is held by its own ticket's tests against a real row (#76).
    return [(template, entry) for template, entry in route_templates() if kind(entry) == route_kind and "<" not in template and entry.name not in ACTS]


def public_pages():
    return [(path, entry) for path, entry in routes_of(PUBLIC) if entry.name not in PUBLIC_POSTS]


def as_a_page(response):
    """The response to a GET, or the test skipped where the route answers POST alone and so is no page (#76)."""
    if response.status_code == 405:
        pytest.skip("answers POST alone, so is no page")
    return response
