# TMDB's image CDN needs no key, so a page links posters straight from it (#5).
POSTER_CDN = "https://image.tmdb.org/t/p/"
POSTER_WIDTHS = {"thumb": "w92", "tile": "w185", "card": "w342"}


def poster_url(film, size):
    return f"{POSTER_CDN}{POSTER_WIDTHS[size]}{film.poster_path}"
