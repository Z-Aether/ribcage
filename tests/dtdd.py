"""DoesTheDogDie as the tests meet it: payloads built inline on the recordings' shapes, which committed tests never read (#56, #102)."""

import urllib.error

VOCABULARY = {
    "/topics": [
        {"id": 153, "name": "a dog dies", "minimalName": "dog death", "keywords": "dog", "description": "A dog dies.", "topicCategoryId": 1},
        {"id": 158, "name": "a cat dies", "minimalName": "cat death", "keywords": "cat", "description": "", "topicCategoryId": 1},
        {"id": 200, "name": "there's a jump scare", "minimalName": "jump scares", "keywords": "", "description": "", "topicCategoryId": 2},
    ],
    "/topiccategories": [
        {"id": 1, "name": "Animal death", "topicSuperCategoryId": 54},
        {"id": 2, "name": "Startles", "topicSuperCategoryId": 50},
    ],
    "/topicsupercategories": [{"id": 54, "name": "Animals"}, {"id": 50, "name": "Scary stuff"}],
}
VOCABULARY_PATHS = list(VOCABULARY)


def item(item_id, name, year, item_type="Movie"):
    return {"id": item_id, "name": name, "releaseYear": year, "itemTypeId": 15, "itemTypeName": item_type, "tmdbId": None}


def detail(listed, *counts):
    stats = [{"itemId": listed["id"], "topicId": topic, "topicName": f"topic {topic}", "yesSum": yes, "noSum": no} for topic, yes, no in counts]
    return {**listed, "topicItemStats": stats}


class Dtdd:
    """A fake transport: `/items` by TMDB id or by title, each record's detail or a 404, and the vocabulary, logging every path asked."""

    def __init__(self, by_tmdb=None, by_title=None, details=(), vocabulary=VOCABULARY, error=None, on_call=None, remaining=()):
        self.by_tmdb = by_tmdb or {}
        self.by_title = by_title or {}
        self.details = {each["id"]: each for each in details}
        self.vocabulary = vocabulary
        self.error = error
        self.on_call = on_call
        # Each call's x-ratelimit-remaining-minute in turn; once they run out, no header at all (#104).
        self.remaining = list(remaining)
        self.paths = []

    def __call__(self, path, parameters, headers):
        self.paths.append(path)
        if self.on_call is not None:
            self.on_call(path)
        if self.error is not None:
            raise self.error
        headers = {"x-ratelimit-remaining-minute": str(self.remaining.pop(0))} if self.remaining else {}
        try:
            return self.answer(path, parameters), headers
        except urllib.error.HTTPError as error:
            # A 404 carries the count too, as DoesTheDogDie's does (#104).
            error.headers = headers
            raise

    def answer(self, path, parameters):
        if path in self.vocabulary:
            return self.vocabulary[path]
        if path == "/items" and "tmdb" in parameters:
            return self.by_tmdb.get(parameters["tmdb"], [])
        if path == "/items" and "q" in parameters:
            return self.by_title.get(parameters["q"], [])
        item_id = int(path.removeprefix("/items/"))
        if item_id not in self.details:
            # An id with no record answers 404, which the client reads as no such record (#105).
            raise urllib.error.HTTPError(path, 404, "Not Found", None, None)
        return self.details[item_id]
