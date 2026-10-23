import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ribcage.films import client, corpus, tmdb

DTDD_API = "https://www.doesthedogdie.com/api/v3"
# DoesTheDogDie's free tier allows 30 requests a minute; #19 measured this pace as safe.
DTDD_SECONDS_BETWEEN_CALLS = 2.15
# A server error or a dropped connection is retried, so one blip doesn't cost a four-minute run.
ATTEMPTS = 3
SECONDS_BEFORE_ANOTHER_ATTEMPT = 10


class Command(BaseCommand):
    help = "Fetch the seed corpus's TMDB and DoesTheDogDie payloads into fixtures/films/, replacing the last fetch."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("fetchcorpus is a development tool, so it runs only with DEBUG on. Set DEBUG=true in .env.")
        # Redirected on Windows, stdout would be cp1252 and mangle Mārama in a log read as UTF-8 (#50).
        if hasattr(self.stdout, "reconfigure"):
            self.stdout.reconfigure(encoding="utf-8")
        directory = corpus.CORPUS_DIRECTORY
        # The keys come only from the environment, as every setting does, and no recording carries them (#45).
        client = Client(settings.TMDB_API_KEY, settings.DTDD_API_KEY)
        tmdb_recordings, dtdd_recordings, posterless = {}, {}, []
        # Everything is fetched before anything is written, so a failed run leaves the last fetch whole.
        for entry in corpus.read_entries(directory):
            tmdb_recording = {"search": client.tmdb("/search/movie", query=entry.written_title, **tmdb.SEARCH_PARAMETERS)}
            if entry.is_hand_entered:
                tmdb_recording["detail"] = None
                self.stdout.write(f"{entry}: hand-entered, searched only")
            else:
                detail = client.tmdb(f"/movie/{entry.tmdb_id}", **tmdb.DETAIL_PARAMETERS)
                tmdb_recording["detail"] = detail
                dtdd_recordings[entry.recording_name] = record_dtdd(client, detail)
                if not detail.get("poster_path"):
                    posterless.append(entry)
                self.stdout.write(f"{entry}: {detail['title']} ({tmdb.year_of(detail.get('release_date'))})")
            tmdb_recordings[entry.recording_name] = tmdb_recording
        replace_recordings(directory / corpus.TMDB_RECORDINGS, tmdb_recordings)
        replace_recordings(directory / corpus.DTDD_RECORDINGS, dtdd_recordings)
        self.stdout.write(f"Recorded {len(tmdb_recordings)} films into {directory}.")
        self.stdout.write(f"Posterless: {', '.join(map(str, posterless)) or 'none'}")


def record_dtdd(client, detail):
    # Raw, so M5's client can be tested against it: the lookup by id, then a title retry where it finds nothing (#20).
    lookup = client.dtdd("/items", tmdb=detail["id"])
    items = {str(item["id"]): client.dtdd(f"/items/{item['id']}") for item in lookup}
    recording = {"lookup": lookup, "retry": None, "items": items}
    if not any(item.get("topicItemStats") for item in items.values()):
        retry = client.dtdd("/items", q=detail["title"])
        recording["retry"] = retry
        # Every same-named item, whatever its year, so the client's year check has both sides to be tested on.
        for item in retry:
            if normalised(item["name"]) == normalised(detail["title"]) and str(item["id"]) not in items:
                items[str(item["id"])] = client.dtdd(f"/items/{item['id']}")
    return recording


def normalised(title):
    return re.sub(r"[^0-9a-z]", "", title.casefold())


def replace_recordings(directory, recordings):
    # A re-run replaces the last fetch outright, so an entry dropped from the corpus leaves no file behind.
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    for name, recording in recordings.items():
        text = json.dumps(recording, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
        (directory / f"{name}.json").write_text(text, encoding="utf-8", newline="\n")


class Client:
    def __init__(self, tmdb_key, dtdd_key):
        self.tmdb_key = tmdb_key
        self.dtdd_key = dtdd_key
        self.next_dtdd_call = 0.0

    def tmdb(self, path, **parameters):
        parameters, headers = client.authorised(self.tmdb_key, parameters, {"accept": "application/json"})
        return get_json("TMDB", client.TMDB_API, path, parameters, headers)

    def dtdd(self, path, **parameters):
        time.sleep(max(0.0, self.next_dtdd_call - time.monotonic()))
        self.next_dtdd_call = time.monotonic() + DTDD_SECONDS_BETWEEN_CALLS
        headers = {"accept": "application/json", "X-API-KEY": self.dtdd_key}
        return get_json("DoesTheDogDie", DTDD_API, path, parameters, headers)


def get_json(service, base, path, parameters, headers):
    url = f"{base}{path}?{urllib.parse.urlencode(parameters)}"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError) as error:
            status = error.code if isinstance(error, urllib.error.HTTPError) else None
            if attempt == ATTEMPTS or (status is not None and status < 500):
                # The URL can carry the TMDB key, so the error names only the path.
                raise CommandError(
                    f"{service} failed on {path}: {status or type(error).__name__}. Nothing was written."
                ) from None
            time.sleep(SECONDS_BEFORE_ANOTHER_ATTEMPT)
