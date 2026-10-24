"""TMDB and DoesTheDogDie as the seeded instance answers them: from the recordings in fixtures/, never the network (#50, #57, #92, #102)."""

import re

from ribcage.films import corpus

DETAIL_PATH = re.compile(r"^/movie/(?P<tmdb_id>\d+)$")
ITEM_PATH = re.compile(r"^/items/(?P<item_id>\d+)$")


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


class RecordedDtdd:
    """A transport for the DoesTheDogDie client: a lookup by TMDB id, a retry by the film's TMDB title, a record by id, and the vocabulary.

    The recordings are gitignored under DTDD's terms, so a fresh clone has none and every call raises, which the client reads as
    DoesTheDogDie not answering, as it does anything else unrecorded (#40, #57).
    """

    def __init__(self, directory=corpus.CORPUS_DIRECTORY, vocabulary_directory=corpus.VOCABULARY_DIRECTORY):
        self.by_tmdb, self.by_title, self.items, self.vocabulary = {}, {}, {}, {}
        for entry in corpus.read_entries(directory):
            try:
                recording = corpus.read_dtdd(entry, directory)
            except corpus.DtddNotRecorded:
                continue
            self.by_tmdb[entry.tmdb_id] = recording["lookup"]
            # fetchcorpus retried by TMDB's title, which is the title a suggestion keeps (#57).
            if recording["retry"] is not None:
                self.by_title[written(corpus.read_tmdb(entry, directory)["detail"]["title"])] = recording["retry"]
            self.items.update({int(item_id): item for item_id, item in recording["items"].items()})
        try:
            self.vocabulary = corpus.read_vocabulary(vocabulary_directory)
        except corpus.DtddNotRecorded:
            pass

    @property
    def is_recorded(self):
        return bool(self.by_tmdb) and bool(self.vocabulary)

    def answer(self, path, parameters):
        if path == "/items" and "tmdb" in parameters and int(parameters["tmdb"]) in self.by_tmdb:
            return self.by_tmdb[int(parameters["tmdb"])]
        if path == "/items" and "q" in parameters and written(parameters["q"]) in self.by_title:
            return self.by_title[written(parameters["q"])]
        if (match := ITEM_PATH.match(path)) and int(match["item_id"]) in self.items:
            return self.items[int(match["item_id"])]
        if path in self.vocabulary:
            return self.vocabulary[path]
        raise NotRecorded(path)

    def __call__(self, path, parameters, headers):
        # No rate-limit header, which the client reads as no limit in sight (#101).
        return self.answer(path, parameters), {}
