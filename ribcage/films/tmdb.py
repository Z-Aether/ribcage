from dataclasses import dataclass

from ribcage.films.film import Film, RuntimeSource

# The one detail call #5 settled; search cannot be skipped, as it returns no runtime.
DETAIL_PARAMETERS = {"language": "en-US", "append_to_response": "credits,videos,release_dates"}
SEARCH_PARAMETERS = {"language": "en-US"}
CERTIFICATE_COUNTRY = "US"


@dataclass(frozen=True)
class SearchResult:
    """One film a TMDB search returned, in TMDB's order, which a person picks from and never trusts (#5)."""

    tmdb_id: int
    title: str
    original_title: str
    year: int | None
    poster_path: str | None


def search_results(search):
    return tuple(
        SearchResult(
            tmdb_id=result["id"],
            title=result["title"],
            original_title=result["original_title"],
            year=year_of(result.get("release_date")),
            poster_path=result.get("poster_path") or None,
        )
        for result in search["results"]
    )


def film_from_detail(detail):
    return Film(
        tmdb_id=detail["id"],
        title=detail["title"],
        original_title=detail["original_title"],
        year=year_of(detail.get("release_date")),
        directors=tuple(person["name"] for person in detail["credits"]["crew"] if person["job"] == "Director"),
        certificate=certificate_of(detail["release_dates"]["results"]),
        trailer_key=trailer_key_of(detail["videos"]["results"]),
        # TMDB guarantees no runtime and writes 0 for an unknown one (#5).
        runtime=detail.get("runtime") or None,
        runtime_source=RuntimeSource.TMDB,
        poster_path=detail.get("poster_path") or None,
        imdb_id=detail.get("imdb_id") or None,
    )


def year_of(release_date):
    return int(release_date[:4]) if release_date else None


def certificate_of(release_dates):
    for country in release_dates:
        if country["iso_3166_1"] == CERTIFICATE_COUNTRY:
            for release in country["release_dates"]:
                if release["certification"]:
                    return release["certification"]
    return None


def trailer_key_of(videos):
    trailers = [video for video in videos if video["site"] == "YouTube" and video["type"] == "Trailer"]
    # An official trailer beats a fan upload; TMDB's own order means nothing.
    trailers.sort(key=lambda video: not video.get("official", False))
    return trailers[0]["key"] if trailers else None
