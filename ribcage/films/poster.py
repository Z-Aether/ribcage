import hashlib

# TMDB's image CDN needs no key, so a page links posters straight from it (#5).
POSTER_CDN = "https://image.tmdb.org/t/p/"
POSTER_WIDTHS = {"thumb": "w92", "tile": "w185", "card": "w342"}
# The theme draws this many muted fills for the title card, numbered from 0.
TITLE_CARD_FILLS = 8


def poster_url(film, size):
    return f"{POSTER_CDN}{POSTER_WIDTHS[size]}{film.poster_path}"


def title_card_fill(film):
    """Which of the theme's fills a film's title card takes: a pure function of the film, so neighbours differ (#38)."""
    # sha256 rather than hash(), which Python salts per process.
    identity = f"tmdb {film.tmdb_id}" if film.tmdb_id is not None else f"hand-entered {film.title} {film.year}"
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % TITLE_CARD_FILLS
