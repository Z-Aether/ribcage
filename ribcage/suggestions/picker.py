"""The picker for what a voter typed in find: TMDB's results as tiles, each film already in the pool marked (#21, #26 §3, #92)."""

from ribcage.films import find
from ribcage.films.client import NotAnswering
from ribcage.films.picker import Picker, PickerTile
from ribcage.suggestions.models import Suggestion


def the_picker(text, tmdb, viewer):
    if not text.strip():
        return Picker()
    try:
        results = find.find(text, tmdb.search)
    except NotAnswering:
        return Picker(searched=True, outage=True)
    in_the_pool = {
        suggestion.tmdb_id: suggestion
        for suggestion in Suggestion.objects.filter(tmdb_id__in=[result.tmdb_id for result in results]).only(
            "pk", "tmdb_id", "suggester_id", "suggester_name"
        )
    }
    return Picker(searched=True, tiles=tuple(tile(result, in_the_pool.get(result.tmdb_id), viewer) for result in results))


def tile(result, suggestion, viewer):
    if suggestion is None:
        return PickerTile(result)
    # The kept name, so a removed suggester's film still says who put it forward (#26, #28).
    yours = suggestion.suggester_id == viewer.pk
    return PickerTile(result, suggested_by=suggestion.suggester_name, suggestion_id=suggestion.pk, yours=yours)
