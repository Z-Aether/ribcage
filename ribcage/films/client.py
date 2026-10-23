"""The TMDB client, the app's one outbound call: on the server alone, plain urllib, en-US, never trusted (#5, #16, #38, #92)."""

import json
import urllib.parse
import urllib.request

from django.conf import settings

from ribcage.films import tmdb

TMDB_API = "https://api.themoviedb.org/3"
# A voter waits on this as they type, so a slow TMDB reads as one not answering (#21).
TIMEOUT_SECONDS = 5

# What the seeded instance answers TMDB from instead of the network, with DEBUG on alone (#50, #92).
stand_in = None


class NotAnswering(Exception):
    """TMDB didn't answer: a timeout, a refused key and any other failure alike (#21, #92)."""


def authorised(key, parameters, headers):
    """The key on a request by fetchcorpus's rule: a v4 read token has two dots and goes in a header (#57)."""
    if key.count(".") == 2:
        return parameters, {**headers, "Authorization": f"Bearer {key}"}
    return {**parameters, "api_key": key}, headers


def over_the_network(path, parameters, headers):
    url = f"{TMDB_API}{path}?{urllib.parse.urlencode(parameters)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


class Client:
    def __init__(self, key, transport=over_the_network):
        self.key = key
        self.transport = transport

    def get(self, path, **parameters):
        parameters, headers = authorised(self.key, parameters, {"accept": "application/json"})
        try:
            answer = self.transport(path, parameters, headers)
        except Exception:
            # The URL can carry the key, so the error names only the path, and drops what it was raised from (#16, #57).
            raise NotAnswering(f"TMDB failed on {path}.") from None
        if not isinstance(answer, dict):
            raise NotAnswering(f"TMDB failed on {path}.")
        return answer

    def search(self, title):
        # Movies alone, never TV or multi search (#21).
        answer = self.get("/search/movie", query=title, **tmdb.SEARCH_PARAMETERS)
        if not isinstance(answer.get("results"), list):
            raise NotAnswering("TMDB failed on /search/movie.")
        try:
            tmdb.search_results(answer)
        except Exception:
            # A result that is malformed reads as TMDB not answering, never as a 500 (#21, #92).
            raise NotAnswering("TMDB failed on /search/movie.") from None
        return answer

    def detail(self, tmdb_id):
        return self.get(f"/movie/{tmdb_id}", **tmdb.DETAIL_PARAMETERS)

    def film(self, tmdb_id):
        """The film as the one detail fetch gives it, read by film_from_detail (#5, #93)."""
        detail = self.detail(tmdb_id)
        try:
            return tmdb.film_from_detail(detail)
        except Exception:
            # A malformed detail reads as TMDB not answering, never as a 500, as a malformed search does (#92).
            raise NotAnswering(f"TMDB failed on /movie/{tmdb_id}.") from None


def answer_from(transport):
    """Answer TMDB from `transport` rather than the network, as the seeded instance does from its recordings (#92)."""
    global stand_in
    stand_in = transport


def tmdb_client():
    # The deployment never sets DEBUG, so it always reaches the real TMDB (#50).
    transport = stand_in if settings.DEBUG and stand_in is not None else over_the_network
    return Client(settings.TMDB_API_KEY, transport)
