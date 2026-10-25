from dataclasses import replace

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_safe

from ribcage.ballot import board, cardbar, done, placing
from ribcage.phase.check import phase_window
from ribcage.phase.history import current
from ribcage.phase.order import Phase
from ribcage.reload import reload_the_tab
from ribcage.suggestions import notes, pool, withdrawal
from ribcage.suggestions.models import Suggestion


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
    # The tile is drawn again where it landed, since the Veto band's row is not a band's tile (#120).
    context = {"counts": board.counts_of(request.user), "oob": True, "tile": board.one_tile(request.user, suggestion), "row": target == placing.VETO}
    return render(request, "ballot/counts.html", context)


def opened_card(request, suggestion):
    """The film's card as VOTE opens it for the viewer: the pool's card, with the ballot's bar (#9, #122)."""
    # Loaded with its holds, as every load that feeds `withdrawable` is (#89, #118).
    held = withdrawal.with_holds(Suggestion.objects.filter(pk=suggestion.pk)).get()
    return pool.the_card(held, request.user, Phase.VOTE)


def board_place(viewer, suggestion):
    """Where the film's tile stands now, for the answer that moves an opened card there (#122)."""
    place, before = board.standing(viewer, suggestion)
    return {"place": place, "before": before}


SEEN_STATES = {"1": True, "0": False}


@phase_window(Phase.VOTE)
@require_POST
def seen(request):
    """Seen it set to the state the post names, and the film's tile or veto frame drawn again; a stale post reloads the ballot as it is (#10, #34, #78, #121)."""
    state = SEEN_STATES.get(request.POST.get("seen"))
    suggestion = candidate(request.POST.get("suggestion"))
    if suggestion is None or state is None:
        return reload_the_tab(request, reverse("phase_page"))
    vetoed = placing.mark_seen(request.user, suggestion, state)
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    if request.POST.get("card"):
        return render(request, "components/vote_seen.html", {"card": opened_card(request, suggestion), "oob": False})
    return render(request, "ballot/seen.html", {"tile": board.one_tile(request.user, suggestion), "row": vetoed, "oob": True})


@phase_window(Phase.VOTE)
@require_POST
def veto_reason(request):
    """The reason on the voter's own veto, kept as a note is; a film they no longer veto reloads the ballot as it is (#10, #88, #120)."""
    suggestion = candidate(request.POST.get("suggestion"))
    if suggestion is None:
        return reload_the_tab(request, reverse("phase_page"))
    typed = request.POST.get("text", "")
    refusal = None
    try:
        kept = placing.give_reason(request.user, suggestion, typed)
    except notes.TooLong as too_long:
        kept, refusal = True, too_long
    if not kept:
        return reload_the_tab(request, reverse("phase_page"))
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    if request.POST.get("card"):
        vote = cardbar.of(request.user, suggestion)
        vote = replace(vote, reason=typed, said=notes.too_long(refusal, False), refused=True) if refusal else replace(vote, said="Saved." if vote.reason else "Cleared.")
        return render(request, "components/vote_reason.html", {"card": replace(opened_card(request, suggestion), vote=vote)})
    tile = board.one_tile(request.user, suggestion)
    if refusal:
        tile = replace(tile, reason=typed, said=notes.too_long(refusal, False), refused=True)
    else:
        tile = replace(tile, said="Saved." if tile.reason else "Cleared.")
    return render(request, "ballot/tile.html", {"tile": tile, "row": True})


@require_safe
def card(request):
    """A tile opens as its card where it stands, or an opened card closes to its tile; a card named in `closes` is closed in the same answer (#9, #21, #122)."""
    if request.headers.get("HX-Request") != "true":
        return redirect("phase_page")
    suggestion = candidate(request.GET.get("suggestion"))
    if suggestion is None or current() != Phase.VOTE:
        return reload_the_tab(request, reverse("phase_page"))
    if "close" in request.GET:
        tile = board.one_tile(request.user, suggestion)
        return render(request, "ballot/tile.html", {"tile": tile, "row": tile.vetoed})
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
