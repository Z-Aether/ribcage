"""TMDB as the seeded instance answers it: from the recordings in fixtures/films/, never the network (#50, #57, #92)."""

import re

from ribcage.films import corpus

DETAIL_PATH = re.compile(r"^/movie/(?P<tmdb_id>\d+)$")


class NotRecorded(LookupError):
    pass


def written(title):
    return " ".join(title.split()).casefold()


class RecordedTmdb:
    """A transport for the TMDB client: a search matches a corpus entry's written title, a detail its TMDB id.

    Anything unrecorded raises, so the client reads it as TMDB not answering, which also shows the outage message.
    """

    def __init__(self, directory=corpus.CORPUS_DIRECTORY):
        self.searches, self.details = {}, {}
        for entry in corpus.read_entries(directory):
            recording = corpus.read_tmdb(entry, directory)
            self.searches[written(entry.written_title)] = recording["search"]
            if recording["detail"] is not None:
                self.details[entry.tmdb_id] = recording["detail"]

    def __call__(self, path, parameters, headers):
        if path == "/search/movie" and written(parameters["query"]) in self.searches:
            return self.searches[written(parameters["query"])]
        if (match := DETAIL_PATH.match(path)) and int(match["tmdb_id"]) in self.details:
            return self.details[int(match["tmdb_id"])]
        raise NotRecorded(path)
