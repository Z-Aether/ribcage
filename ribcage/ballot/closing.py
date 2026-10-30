"""The answer that closes VOTE's opened card to its tile where it stands (#132, #150)."""

from django.shortcuts import render

from ribcage.ballot import board


def to_tile(request, suggestion):
    """The film's tile, retargeted over the card the post came from, so a saved note closes the card as its title does."""
    answer = render(request, "components/ballot_tile.html", {"tile": board.one_tile(request.user, suggestion)})
    answer.headers["HX-Retarget"] = f'li.card-item[data-suggestion="{suggestion.pk}"]'
    answer.headers["HX-Reswap"] = "outerHTML"
    return answer
