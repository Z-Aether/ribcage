"""Correcting a match: anyone pastes a DoesTheDogDie link, sees the record it names, and Use this match saves it signed (#32 §5, #105)."""

import html
import re
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from ribcage.identity.removal import remove
from ribcage.phase.order import PHASES, Phase
from ribcage.suggestions.models import Suggestion
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import correction, fetch, status
from ribcage.triggers.models import TriggerData
from tests.dtdd import Dtdd, detail, item
from tests.films import CABINET_OF_CURIOSITIES, a_tmdb_film
from tests.http.test_phase import walk_to

MATCH, ADMIN_MATCH, TAB = "/dtdd/match/", "/console/films/dtdd/match/", "/console/films/"
HTMX = {"HX-Request": "true"}
SUGGEST, APPROVE, VOTE, PICK, RUN = Phase
WINDOW = [SUGGEST, APPROVE, VOTE]
OUTSIDE_THE_WINDOW = [PICK, RUN]

EXIT_8 = item(1558416, "Exit 8", 2025)
ITS_EMPTY_DUPLICATE = item(1362774, "８番出口", 2025)
# Werewolf by Night's real record has no year, so the automatic lookup leaves the film uncovered on an empty one (#62).
WEREWOLF_EMPTY, WEREWOLF_REAL = item(1210242, "Werewolf By Night", 2022), item(834224, "Werewolf by Night", None)
A_SERIES = item(777, "Cabinet of Curiosities", 2022, item_type="TV Show")
DETAILS = [
    detail(EXIT_8, (153, 3, 1), (200, 40, 2), (999, 5, 0), (158, 0, 12)),
    detail(ITS_EMPTY_DUPLICATE),
    detail(WEREWOLF_EMPTY),
    detail(WEREWOLF_REAL, (158, 9, 0)),
    detail(A_SERIES, (200, 2, 0)),
]


def link(listed):
    return f"https://www.doesthedogdie.com/media/{listed['id']}"


@pytest.fixture
def dtdd(monkeypatch):
    """DoesTheDogDie as every request in the test meets it, logging what each asks."""
    answering = Dtdd(details=DETAILS)
    monkeypatch.setattr(dtdd_client, "over_the_network", answering)
    return answering


@pytest.fixture
def films(voters, dtdd):
    """Exit 8 matched `auto` to its empty duplicate, as the seed has it; Werewolf by Night uncovered; Cabinet by hand (#57).

    The first lookup stores the vocabulary too, as on a fresh database (#62).
    """
    ada = voters["ada"]
    exit_8 = Suggestion.objects.suggest(ada, a_tmdb_film(1408208, "Exit 8"), "Pitch.")
    werewolf = Suggestion.objects.suggest(ada, a_tmdb_film(894205, "Werewolf by Night"), "Pitch.")
    cabinet = Suggestion.objects.suggest(ada, CABINET_OF_CURIOSITIES, "Pitch.")
    lookups = Dtdd(by_tmdb={1408208: [ITS_EMPTY_DUPLICATE], 894205: [WEREWOLF_EMPTY]}, details=DETAILS)
    for suggestion in (exit_8, werewolf):
        fetch.look_up(suggestion, dtdd_client.Client("key", lookups))
    dtdd.paths.clear()
    return {"exit 8": exit_8, "werewolf": werewolf, "cabinet": cabinet}


@pytest.fixture
def hanna(voters):
    client = Client()
    client.force_login(voters["Hanna"])
    return client


def ask(client, suggestion, pasted, route=MATCH):
    return client.get(route, {"suggestion": suggestion.pk, "link": pasted}, headers=HTMX)


def use(client, suggestion, signed, route=MATCH, headers=HTMX):
    return client.post(route, {"suggestion": suggestion.pk, "snapshot": signed}, headers=headers)


def signed_in(preview):
    return html.unescape(re.search(r'<input type="hidden" name="snapshot" value="([^"]*)">', preview)[1])


def stored_match(suggestion):
    row = TriggerData.objects.filter(suggestion=suggestion).first()
    return None if row is None else (row.match, row.match_set_by)


def text(fragment):
    words = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())
    return re.sub(r" (?=[,.])", "", words)


def section_of(page, suggestion):
    card = re.search(rf'data-suggestion="{suggestion.pk}".*?</article>', page, re.S)[0]
    return re.search(r'<section class="film-card__dtdd.*?</section>', card, re.S)[0]


def control_of(fragment):
    return re.search(r'<div class="dtdd__matching[^"]*"[^>]*>', fragment)[0]


def as_answered(section):
    # The page's control is kept across a note's swap; the control's own answer to the same state replaces it (#105).
    return section.replace(" hx-preserve>", ">", 1) if 'class="dtdd__matching' in section else section


# The control on the match line


def test_a_matched_film_asks_if_it_is_the_wrong_film_and_links_to_dtdds_search(hanna, films, dtdd):
    corrected = films["exit 8"]
    use(hanna, corrected, signed_in(ask(hanna, corrected, link(EXIT_8)).text))

    shown = section_of(hanna.get("/").text, corrected)

    assert "Wrong film? Find it on DoesTheDogDie ↗, then paste its link here." in text(shown)
    assert '<a href="https://www.doesthedogdie.com/" target="_blank" rel="noopener">Find it on DoesTheDogDie&nbsp;↗</a>' in shown


@pytest.mark.parametrize("film", ["exit 8", "werewolf", "cabinet"], ids=["uncovered on an empty record", "uncovered", "no match"])
def test_any_other_film_offers_the_same_control_without_asking(hanna, films, film):
    shown = section_of(hanna.get("/").text, films[film])

    assert "Find it on DoesTheDogDie ↗, then paste its link here." in text(shown)
    assert "Wrong film?" not in shown
    assert re.search(rf'<form class="dtdd__correct" method="get" action="{MATCH}" hx-get="{MATCH}"', shown)


def test_a_not_fetched_film_offers_it_too(hanna, voters, dtdd):
    weapons = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(1078605, "Weapons"), "Pitch.")

    assert "Find it on DoesTheDogDie" in section_of(hanna.get("/").text, weapons)


# The preview


def test_a_pasted_link_previews_its_record_by_one_fetch_and_writes_nothing(hanna, films, dtdd):
    before = stored_match(films["exit 8"])

    preview = ask(hanna, films["exit 8"], link(EXIT_8)).text

    # Topic 999 isn't named by the vocabulary and 158 has no yes vote, so neither is counted, as the card won't list them (#62, #103).
    assert "Found: Exit 8 (2025) ↗ · Movie · 2 topics" in text(preview)
    assert '<button type="submit" autofocus>Use this match</button>' in preview
    assert ">Cancel</a>" in preview
    assert "Powered by DoesTheDogDie.com" in preview
    assert dtdd.paths == ["/items/1558416"]
    assert stored_match(films["exit 8"]) == before


@pytest.mark.parametrize(
    "pasted",
    ["https://www.doesthedogdie.com/media/777", "doesthedogdie.com/media/777/", " https://www.doesthedogdie.com/media/777?x=1 "],
)
def test_any_item_type_previews_however_its_link_was_copied(hanna, films, pasted):
    # A series added by hand is a "TV Show" there (#19).
    assert "Found: Cabinet of Curiosities (2022) ↗ · TV Show" in text(ask(hanna, films["cabinet"], pasted).text)


def test_a_record_with_no_year_previews_without_one(hanna, films):
    assert "Found: Werewolf by Night ↗ · Movie · 1 topic Use this match" in text(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text)


def test_a_preview_on_a_film_credited_for_nothing_else_carries_the_credit_in_the_control(hanna, films):
    # Inside the control, so the credit stays with a preview a note's swap keeps (#21, #105).
    preview = ask(hanna, films["cabinet"], "https://www.doesthedogdie.com/media/777").text
    control = re.search(r'<div class="dtdd__matching.*?</div>', preview, re.S)[0]

    assert preview.count("Powered by DoesTheDogDie.com") == 1
    assert "Powered by DoesTheDogDie.com" in control


def test_the_preview_the_card_and_the_films_tab_count_the_same_topics(hanna, films, admin):
    exit_8 = films["exit 8"]
    preview = ask(hanna, exit_8, link(EXIT_8)).text
    use(hanna, exit_8, signed_in(preview))

    on_the_tab = re.search(rf'id="film-{exit_8.pk}".*?(\d+ topics?)', admin.get(TAB).text, re.S)[1]
    assert "Movie · 2 topics" in text(preview)
    assert "All 2 topics" in section_of(hanna.get("/").text, exit_8)
    assert on_the_tab == "2 topics"


# Across a note's swap of the card


def test_a_notes_swap_of_the_card_keeps_the_control_as_it_was_under_an_id_naming_the_film_and_its_match(hanna, films):
    # htmx keeps an hx-preserve element where the swapped-in card has one of its id, so a pasted link or a preview survives (#105).
    exit_8 = films["exit 8"]
    page = hanna.get("/").text

    swapped = hanna.post("/note/", {"suggestion": exit_8.pk, "text": "I'm in."}, headers=HTMX).text

    kept = f'<div class="dtdd__matching" id="dtdd-matching-{exit_8.pk}-1362774" hx-preserve>'
    assert control_of(swapped) == kept
    assert control_of(section_of(page, exit_8)) == kept
    assert page.count(f'id="dtdd-matching-{exit_8.pk}-1362774"') == 1


def test_a_film_with_no_match_names_none_in_the_controls_id(hanna, films):
    cabinet = films["cabinet"]

    assert control_of(section_of(hanna.get("/").text, cabinet)) == f'<div class="dtdd__matching" id="dtdd-matching-{cabinet.pk}-" hx-preserve>'


@pytest.mark.parametrize(
    "answer",
    [
        lambda client, films: ask(client, films["exit 8"], link(EXIT_8)),
        lambda client, films: ask(client, films["exit 8"], "not a link"),
        lambda client, films: client.get(MATCH, {"suggestion": films["exit 8"].pk, "cancel": ""}, headers=HTMX),
        lambda client, films: use(client, films["exit 8"], signed_in(ask(client, films["exit 8"], link(EXIT_8)).text)),
    ],
    ids=["a preview", "a refusal", "cancel", "use this match"],
)
def test_the_controls_own_answers_replace_it(hanna, films, answer):
    control = control_of(answer(hanna, films).text)

    assert f'id="dtdd-matching-{films["exit 8"].pk}-' in control
    assert "hx-preserve" not in control


@pytest.mark.parametrize("asking", [True, False], ids=["a preview", "cancel"])
def test_the_admins_answers_replace_the_control_too(admin, films, asking):
    exit_8 = films["exit 8"]
    params = {"suggestion": exit_8.pk, "link": link(EXIT_8)} if asking else {"suggestion": exit_8.pk, "cancel": ""}

    answered = admin.get(ADMIN_MATCH, params, headers=HTMX).text

    assert control_of(answered) == f'<div class="dtdd__matching{" is-previewing" if asking else ""}" id="dtdd-matching-{exit_8.pk}-1362774">'


def test_cancel_puts_the_line_back_as_it_is_and_fetches_nothing(hanna, films, dtdd):
    pool_section = section_of(hanna.get("/").text, films["exit 8"])

    cancelled = hanna.get(MATCH, {"suggestion": films["exit 8"].pk, "cancel": ""}, headers=HTMX).text

    assert cancelled.strip() == as_answered(pool_section).strip()
    assert dtdd.paths == []


# Use this match


def test_use_this_match_stores_the_signed_snapshot_set_by_the_voter_fetched_now(hanna, films, dtdd):
    werewolf = films["werewolf"]
    signed = signed_in(ask(hanna, werewolf, link(WEREWOLF_REAL)).text)

    use(hanna, werewolf, signed)

    row = TriggerData.objects.get(suggestion=werewolf)
    assert (row.match, row.match_set_by) == (834224, "Hanna")
    fetched = status.from_text(row.snapshot)
    assert fetched.snapshot.record.name == "Werewolf by Night"
    assert [(count.topic_id, count.yes, count.no) for count in fetched.snapshot.counts] == [(158, 9, 0)]
    assert timezone.now() - fetched.fetched_at < timedelta(minutes=1)


def test_the_save_makes_no_call_to_dtdd(hanna, films, dtdd):
    signed = signed_in(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text)
    dtdd.paths.clear()
    dtdd.error = ConnectionError("DoesTheDogDie is down")

    response = use(hanna, films["werewolf"], signed)

    assert response.status_code == 200
    assert dtdd.paths == []
    assert stored_match(films["werewolf"]) == (834224, "Hanna")


def test_the_section_swaps_in_place_with_the_new_match_and_its_topics(hanna, films, dtdd):
    exit_8 = films["exit 8"]
    before = section_of(hanna.get("/").text, exit_8)

    swapped = use(hanna, exit_8, signed_in(ask(hanna, exit_8, link(EXIT_8)).text)).text

    assert "DTDD: ８番出口 (2025) ↗ · auto" in text(before) and "uncovered" in before
    assert swapped.lstrip().startswith('<section class="film-card__dtdd dtdd dtdd--matched"')
    assert "DTDD: Exit 8 (2025) ↗ · set by Hanna" in text(swapped)
    assert "All 2 topics on DoesTheDogDie" in swapped
    # A new id, so htmx brings the new record's list in rather than preserving the old one (#103).
    assert f'id="dtdd-topics-{exit_8.pk}-1558416" hx-preserve' in swapped
    # The poster rides along out of band, for its ring (#111).
    assert as_answered(section_of(hanna.get("/").text, exit_8)).strip() == swapped.split('<div class="film-card__poster')[0].strip()
    assert f'id="film-card-poster-{exit_8.pk}" hx-swap-oob="outerHTML"' in swapped


def test_a_plain_post_saves_and_lands_on_the_pool(hanna, films):
    signed = signed_in(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text)

    response = use(hanna, films["werewolf"], signed, headers={})

    assert response.status_code == 302 and response.url == "/"
    assert stored_match(films["werewolf"]) == (834224, "Hanna")


def test_a_match_can_be_set_back_to_the_record_it_had(hanna, films):
    exit_8 = films["exit 8"]
    use(hanna, exit_8, signed_in(ask(hanna, exit_8, link(EXIT_8)).text))

    use(hanna, exit_8, signed_in(ask(hanna, exit_8, link(ITS_EMPTY_DUPLICATE)).text))

    assert stored_match(exit_8) == (1362774, "Hanna")


def tampered(value):
    middle = len(value) // 3
    return value[:middle] + ("A" if value[middle] != "A" else "B") + value[middle + 1 :]


@pytest.mark.parametrize("how", ["altered", "another film's", "missing"])
def test_a_tampered_or_another_films_signed_snapshot_is_refused_and_writes_nothing(hanna, films, how):
    werewolf, exit_8 = films["werewolf"], films["exit 8"]
    for_werewolf = signed_in(ask(hanna, werewolf, link(WEREWOLF_REAL)).text)
    signed = {"altered": tampered(for_werewolf), "another film's": for_werewolf, "missing": ""}[how]
    target = exit_8 if how == "another film's" else werewolf
    before = stored_match(target)

    response = use(hanna, target, signed)

    assert response.status_code == 400
    assert stored_match(target) == before


def test_a_film_withdrawn_since_reloads_the_tab(hanna, films):
    signed = signed_in(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text)
    pk = films["werewolf"].pk
    films["werewolf"].delete()

    asked = hanna.get(MATCH, {"suggestion": pk, "link": link(WEREWOLF_REAL)}, headers=HTMX)
    used = hanna.post(MATCH, {"suggestion": pk, "snapshot": signed}, headers=HTMX)

    assert asked.headers["HX-Redirect"] == used.headers["HX-Redirect"] == "/"
    assert not TriggerData.objects.filter(suggestion_id=pk).exists()


# Refusals


@pytest.mark.parametrize(
    "pasted",
    ["Werewolf by Night", "https://www.imdb.com/title/tt15318872/", "https://www.doesthedogdie.com/search?q=werewolf"],
)
def test_not_a_dtdd_link_is_refused_gently_with_the_pasted_text_kept(hanna, films, dtdd, pasted):
    refused = ask(hanna, films["werewolf"], pasted).text

    assert html.unescape(re.search(r'<input type="text" name="link" value="([^"]*)"', refused)[1]) == pasted
    assert html.unescape(correction.NOT_A_LINK) in html.unescape(refused)
    assert 'class="dtdd__refusal"' in refused
    assert "Use this match" not in refused
    assert dtdd.paths == []


@pytest.mark.parametrize(
    "error, says",
    [(None, correction.NO_SUCH_RECORD), (ConnectionError("down"), correction.NOT_ANSWERING)],
    ids=["no such record", "not answering"],
)
def test_no_such_record_or_dtdd_not_answering_is_refused_with_the_pasted_text_kept(hanna, films, dtdd, error, says):
    dtdd.error = error
    pasted = "https://www.doesthedogdie.com/media/424242"
    before = stored_match(films["werewolf"])

    refused = ask(hanna, films["werewolf"], pasted).text

    assert re.search(r'<input type="text" name="link" value="([^"]*)"', refused)[1] == pasted
    assert html.unescape(says) in html.unescape(refused)
    assert stored_match(films["werewolf"]) == before


# Who, and when


@pytest.mark.parametrize("phase", WINDOW)
def test_a_voter_previews_and_saves_in_suggest_approve_and_vote(hanna, films, phase):
    walk_to(phase)

    signed = signed_in(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text)
    response = use(hanna, films["werewolf"], signed)

    assert response.status_code == 200
    assert stored_match(films["werewolf"]) == (834224, "Hanna")


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
def test_a_voters_preview_is_refused_outside_the_window_reloading_the_tab(hanna, films, dtdd, phase):
    walk_to(phase)

    response = ask(hanna, films["werewolf"], link(WEREWOLF_REAL))

    assert response.headers["HX-Redirect"] == "/"
    assert dtdd.paths == []


@pytest.mark.parametrize("phase", OUTSIDE_THE_WINDOW)
@pytest.mark.parametrize("headers, lands", [(HTMX, "HX-Redirect"), ({}, "Location")], ids=["htmx", "plain"])
def test_a_voters_stale_save_from_outside_the_window_writes_nothing_and_reloads_the_tab(hanna, films, phase, headers, lands):
    signed = signed_in(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text)
    before = stored_match(films["werewolf"])
    walk_to(phase)

    response = use(hanna, films["werewolf"], signed, headers=headers)

    assert response.headers[lands] == "/"
    assert stored_match(films["werewolf"]) == before


def test_a_plain_get_lands_on_the_pool(hanna, films):
    response = hanna.get(MATCH, {"suggestion": films["werewolf"].pk, "link": link(WEREWOLF_REAL)})

    assert response.status_code == 302 and response.url == "/"


@pytest.mark.parametrize("phase", [SUGGEST, APPROVE, VOTE, PICK])
def test_the_admin_previews_and_saves_under_a_films_tab_row_in_every_phase_from_suggest_to_pick(admin, films, dtdd, phase):
    walk_to(phase)
    row = re.search(rf'<tr class="ledger__detail" id="film-{films["exit 8"].pk}" hidden>(.*?)</tr>', admin.get(TAB).text, re.S)[1]
    assert re.search(rf'<form class="dtdd__correct" method="get" action="{ADMIN_MATCH}"', row)

    preview = ask(admin, films["exit 8"], link(EXIT_8), route=ADMIN_MATCH).text
    assert "Found: Exit 8 (2025) ↗ · Movie" in text(preview)
    assert f'hx-post="{ADMIN_MATCH}"' in preview
    swapped = use(admin, films["exit 8"], signed_in(preview), route=ADMIN_MATCH).text

    assert stored_match(films["exit 8"]) == (1558416, correction.BY_THE_ADMIN)
    assert "DTDD: Exit 8 (2025) ↗ · set by the admin" in text(swapped)
    # The swapped section lists from the console's own routes, behind the admin's wall.
    assert f'hx-get="/console/films/dtdd/?suggestion={films["exit 8"].pk}"' in swapped


def test_the_admins_refusals_keep_the_pasted_text_too(admin, films):
    refused = ask(admin, films["werewolf"], "not a link", route=ADMIN_MATCH).text

    assert 'value="not a link"' in refused
    assert html.unescape(correction.NOT_A_LINK) in html.unescape(refused)


def test_the_admin_refuses_a_tampered_snapshot(admin, hanna, films):
    signed = signed_in(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text)

    assert use(admin, films["exit 8"], signed, route=ADMIN_MATCH).status_code == 400
    assert stored_match(films["exit 8"]) == (1362774, "")


def test_a_voters_signed_snapshot_is_the_admins_to_use_and_the_other_way_round(admin, hanna, films):
    # One control for everyone: the preview carries the record, not who asked (#32 §5).
    from_hanna = signed_in(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text)
    from_the_admin = signed_in(ask(admin, films["exit 8"], link(EXIT_8), route=ADMIN_MATCH).text)

    use(admin, films["werewolf"], from_hanna, route=ADMIN_MATCH)
    use(hanna, films["exit 8"], from_the_admin)

    assert stored_match(films["werewolf"]) == (834224, correction.BY_THE_ADMIN)
    assert stored_match(films["exit 8"]) == (1558416, "Hanna")


def test_a_plain_admin_request_lands_on_the_tab(admin, films):
    signed = signed_in(ask(admin, films["werewolf"], link(WEREWOLF_REAL), route=ADMIN_MATCH).text)

    asked = admin.get(ADMIN_MATCH, {"suggestion": films["werewolf"].pk, "link": link(WEREWOLF_REAL)})
    used = use(admin, films["werewolf"], signed, route=ADMIN_MATCH, headers={})

    assert (asked.url, used.url) == (TAB, TAB)
    assert stored_match(films["werewolf"]) == (834224, correction.BY_THE_ADMIN)


@pytest.mark.parametrize("named", ["", "nonsense", "99999"])
def test_the_admins_correction_for_a_film_gone_reloads_the_tab(admin, films, named):
    response = admin.get(ADMIN_MATCH, {"suggestion": named, "link": link(EXIT_8)}, headers=HTMX)

    assert response.headers["HX-Redirect"] == TAB


# Removal


def test_a_removed_setters_kept_name_stays_on_the_tag(hanna, voters, films, admin):
    use(hanna, films["werewolf"], signed_in(ask(hanna, films["werewolf"], link(WEREWOLF_REAL)).text))

    remove(voters["Hanna"])

    assert stored_match(films["werewolf"]) == (834224, "Hanna")
    assert "set by Hanna" in text(admin.get(TAB).text)


def test_every_phase_is_covered():
    assert sorted(WINDOW + OUTSIDE_THE_WINDOW, key=PHASES.index) == list(PHASES)
