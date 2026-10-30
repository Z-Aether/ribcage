from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_safe

from ribcage.ballot import board, done, placing
from ribcage.phase.check import phase_window
from ribcage.phase.history import current
from ribcage.phase.order import Phase
from ribcage.reload import reload_the_tab
from ribcage.suggestions import pool, withdrawal
from ribcage.suggestions.models import Approval, Suggestion


def candidate(posted):
    try:
        return board.candidates().filter(pk=posted).first()
    except (TypeError, ValueError):
        return None


@phase_window(Phase.VOTE)
@require_POST
def place(request):
    """One placement: the film named, put where the post says. A film that is no candidate now, or a target that is none, changes nothing and reloads the ballot as it is (#34, #78, #119)."""
    target = placing.target_of(request.POST.get("to"))
    suggestion = candidate(request.POST.get("suggestion"))
    if suggestion is None or target is None:
        return reload_the_tab(request, reverse("phase_page"))
    placing.place(request.user, suggestion, target)
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    if request.POST.get("card"):
        return render(request, "ballot/moved.html", {"counts": board.counts_of(request.user), "card": opened_card(request, suggestion), **board_place(request.user, suggestion)})
    context = {"counts": board.counts_of(request.user), "oob": True, "tile": board.one_tile(request.user, suggestion)}
    # A film dragged into the Veto band with no note yet opens as its card, as a tile click opens it, and closes the card open before it (#120).
    if target == placing.VETO and placing.needs_a_reason(request.user, suggestion):
        context["card"] = opened_card(request, suggestion)
        other = candidate(request.POST.get("closes"))
        if other is not None and other.pk != suggestion.pk:
            context["closed"] = board.one_tile(request.user, other)
    return render(request, "ballot/counts.html", context)


def opened_card(request, suggestion):
    """The film's card as VOTE opens it for the viewer: the pool's card, with the ballot's bar, whose note box is the pool's (#9, #122, #150)."""
    # Loaded with its holds, as every load that feeds `withdrawable` is (#89, #118).
    held = withdrawal.with_holds(Suggestion.objects.filter(pk=suggestion.pk)).get()
    return pool.the_card(held, request.user, Phase.VOTE)


def board_place(viewer, suggestion):
    """Where the film's tile stands now, for the answer that moves an opened card there (#122)."""
    place, before = board.standing(viewer, suggestion)
    return {"place": place, "before": before}


SEEN_STATES = {"1": True, "0": False}


def pooled(posted):
    """The film a post names in the pool, whatever its approval, loaded with its holds; None for one withdrawn since or no id at all (#152)."""
    try:
        return withdrawal.with_holds(Suggestion.objects.filter(pk=posted)).first()
    except (TypeError, ValueError):
        return None


def row_of(request, suggestion):
    """The answer to a veto or seen it made from an open card: the bar's row alone, with the veto reason's line and the notes list out of band, so the note box and a runtime box are never redrawn (#152).

    The notes list carries the viewer's own mark, which the open card hides and the card shows once closed, so a mark changed here is there when it closes (#128, #153).
    """
    card = pool.the_card(suggestion, request.user, current())
    row = render(request, "components/vote_row.html", {"card": card})
    row.content += render(request, "components/note_hint.html", {"card": card, "oob": True}).content
    row.content += render(request, "components/film_notes.html", {"card": card, "oob": True}).content
    return row


@phase_window(Phase.SUGGEST, Phase.APPROVE)
@require_POST
def veto(request):
    """A veto set or taken back on any film in the pool, scores being VOTE's alone; VOTE's own are the placement's. A film withdrawn since reloads the tab (#10, #34, #78, #152)."""
    state = SEEN_STATES.get(request.POST.get("veto"))
    suggestion = pooled(request.POST.get("suggestion"))
    if suggestion is None or state is None:
        return reload_the_tab(request, reverse("phase_page"))
    placing.set_veto(request.user, suggestion, state)
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    return row_of(request, suggestion)


@phase_window(Phase.SUGGEST, Phase.APPROVE, Phase.VOTE)
@require_POST
def seen(request):
    """Seen it set to the state the post names: on any film in the pool before VOTE, on a candidate in it. The open card's row is drawn again, a tile its tile; a stale post reloads the tab (#10, #34, #78, #121, #152)."""
    state = SEEN_STATES.get(request.POST.get("seen"))
    voting = current() == Phase.VOTE
    suggestion = pooled(request.POST.get("suggestion"))
    if suggestion is None or state is None or (voting and suggestion.approval != Approval.APPROVED):
        return reload_the_tab(request, reverse("phase_page"))
    placing.mark_seen(request.user, suggestion, state)
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    if request.POST.get("card"):
        return row_of(request, suggestion)
    return render(request, "components/ballot_tile.html", {"tile": board.one_tile(request.user, suggestion), "oob": True})


@require_safe
def card(request):
    """A tile opens as its card where it stands, or an opened card closes to its tile; a card named in `closes` is closed in the same answer (#9, #21, #122)."""
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    suggestion = candidate(request.GET.get("suggestion"))
    if suggestion is None or current() != Phase.VOTE:
        return reload_the_tab(request, reverse("phase_page"))
    if "close" in request.GET:
        return render(request, "components/ballot_tile.html", {"tile": board.one_tile(request.user, suggestion)})
    context = {"card": opened_card(request, suggestion), "scroll": True}
    other = candidate(request.GET.get("closes"))
    if other is not None and other.pk != suggestion.pk:
        context["closed"] = board.one_tile(request.user, other)
    return render(request, "ballot/opened.html", context)


DONE_STATES = {"1": True, "0": False}


@phase_window(Phase.VOTE)
@require_POST
def im_done(request):
    """The voter's done marker set to the state the post names, and the header's roster drawn again. A post naming no state, or pressing *I'm done* on a ballot of another size than now, reloads the ballot and writes nothing; unpressing is always safe and needs no size (#15, #34, #78, #119, #123, #124)."""
    state = DONE_STATES.get(request.POST.get("done"))
    size = request.POST.get("size", "")
    if state is None or (state and size != str(board.candidates().count())):
        return reload_the_tab(request, reverse("phase_page"))
    done.set_done(request.user, state)
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    # The size posted is echoed, not the current one, so a stale page stays stale after unpressing (#124).
    return render(request, "ballot/done.html", {"roster": done.roster(request.user), "size": size})
