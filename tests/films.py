"""Films as plain data for the tests that need one without reading the corpus."""

from ribcage.films.film import Film, RuntimeSource, hand_entered

THE_SHINING = Film(
    tmdb_id=694,
    title="The Shining",
    original_title="The Shining",
    year=1980,
    directors=("Stanley Kubrick",),
    certificate="R",
    trailer_key="S014oGZiSdI",
    runtime=144,
    runtime_source=RuntimeSource.TMDB,
    poster_path="/uAR0AWqhQL1hQa69UDEbb2rE5Wx.jpg",
    imdb_id="tt0081505",
)
INFESTED = Film(
    tmdb_id=1063879,
    title="Infested",
    original_title="Vermines",
    year=2023,
    directors=("Sébastien Vaniček",),
    certificate=None,
    trailer_key=None,
    runtime=106,
    runtime_source=RuntimeSource.TMDB,
    poster_path=None,
    imdb_id=None,
)
CABINET_OF_CURIOSITIES = hand_entered("Cabinet of Curiosities", None, 47)


def a_tmdb_film(tmdb_id, title, runtime=100):
    return Film(
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=2000,
        directors=(),
        certificate=None,
        trailer_key=None,
        runtime=runtime,
        runtime_source=RuntimeSource.TMDB,
        poster_path=None,
        imdb_id=None,
    )


def as_loaded(suggestion, held_by_ballot=False, held_by_box=False):
    """A suggestion built in memory, annotated as `withdrawal.with_holds` would (#118)."""
    suggestion.held_by_ballot = held_by_ballot
    suggestion.held_by_box = held_by_box
    return suggestion
