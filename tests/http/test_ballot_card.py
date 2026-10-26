"""A tile opens as its card in VOTE: the shared card with VOTE's phase bar, each control the ballot's own write (#9, #10, #21, #122)."""

import re

import pytest
from django.conf import settings

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Note
from ribcage.triggers import watched
from tests.http.test_ballot_page import HTMX, film, place, region, signed_in, walk_on_to
from tests.http.test_dtdd_credit import Tree
from tests.http.test_matched_topics import DOG, add, dtdd, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

CARD, PLACE, SEEN, REASON = "/ballot/card/", "/ballot/place/", "/ballot/seen/", "/ballot/veto-reason/"


@pytest.fixture
def ballot(voters):
    walk_to(Phase.VOTE)
    hanna = voters["Hanna"]
    return {"voters": voters, "ada": voters["ada"], "client": signed_in(voters["ada"]), "one": film(hanna, "One"), "two": film(hanna, "Two"), "three": film(hanna, "Three")}


def opened(client, suggestion, **extra):
    return client.get(CARD, {"suggestion": str(suggestion.pk), **extra}, headers=HTMX)


def bar_of(page):
    return re.search(r"data-vote-bar>(.*?)\n</div>", page, re.S)[1]


def test_a_plain_get_goes_to_the_phase_page(ballot):
    assert ballot["client"].get(CARD, {"suggestion": str(ballot["one"].pk)}).status_code == 302


def test_an_opened_card_is_the_shared_card_with_no_note_box_and_no_pencil(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Ada wrote this.")
    page = opened(ballot["client"], ballot["one"]).text

    assert f'<li class="card-item" data-suggestion="{ballot["one"].pk}"' in page and "film-card is-open" in page
    assert 'action="/note/"' not in page and 'name="text"' not in page and "runtime__pencil" not in page
    # Every note is read, the viewer's own among them, since no box holds it.
    assert "Ada wrote this." in page and "note--yours" not in page


def test_the_viewers_own_pitch_is_read_on_their_opened_card(ballot):
    own = film(ballot["ada"], "Ada's own")
    Note.objects.create(suggestion=own, author=ballot["ada"], text="Ada pitched this.")
    page = opened(ballot["client"], own).text

    assert "Ada pitched this." in page and "note--yours" not in page


def test_the_bar_marks_the_current_score(ballot):
    place(ballot["client"], ballot["one"], 2)
    bar = bar_of(opened(ballot["client"], ballot["one"]).text)

    assert re.findall(r'score--([a-z-]+) is-current"', bar) == ["keen"]
    assert re.findall(r'aria-pressed="true"', bar) == ['aria-pressed="true"']


def test_a_veto_replaces_the_score_with_minus_two_and_shows_the_reason_box(ballot):
    place(ballot["client"], ballot["one"], "veto")
    page = opened(ballot["client"], ballot["one"]).text
    bar = bar_of(page)

    assert "is-vetoed" in page and "−2" in bar and "data-vote-reason" in bar
    assert not re.search(r"score--(top-pick|keen|happy|dont-mind|rather-not) is-current", bar)


def test_without_a_veto_there_is_no_reason_box(ballot):
    assert "data-vote-reason" not in opened(ballot["client"], ballot["one"]).text


def test_each_score_button_posts_the_ballots_own_place_route(ballot):
    bar = bar_of(opened(ballot["client"], ballot["one"]).text)

    assert bar.count(f'hx-post="{PLACE}"') == 6
    assert re.findall(r'"to": "([^"]+)"', bar) == ["3", "2", "1", "0", "-1", "veto"]
    assert f'hx-post="{SEEN}"' in bar


def test_placing_from_the_card_writes_as_the_drag_does_and_moves_the_card(ballot):
    answer = ballot["client"].post(PLACE, {"suggestion": str(ballot["one"].pk), "to": "3", "card": "1"}, headers=HTMX).text

    assert BallotRecord.objects.get(voter=ballot["ada"], suggestion=ballot["one"]).score == 3
    assert f"hx-swap-oob=\"delete:li[data-suggestion='{ballot['one'].pk}']\"" in answer
    assert "afterbegin:ul[data-place='3']" in answer and "data-scroll-here" in answer
    assert "1 of 3 scored" in answer
    assert region(ballot["client"].get("/").text, "3") == [ballot["one"].pk]


def test_a_card_moved_to_a_band_goes_after_the_tile_before_it(ballot):
    for key in ("one", "two", "three"):
        place(ballot["client"], ballot[key], 1)
    listed = region(ballot["client"].get("/").text, "1")
    answer = ballot["client"].post(PLACE, {"suggestion": str(listed[2]), "to": "1", "card": "1"}, headers=HTMX).text

    assert f"afterend:li[data-suggestion='{listed[1]}']" in answer


def test_vetoing_from_the_card_and_turning_it_off_use_the_same_write(ballot):
    ballot["client"].post(PLACE, {"suggestion": str(ballot["one"].pk), "to": "veto", "card": "1"}, headers=HTMX)
    assert BallotRecord.objects.get(voter=ballot["ada"]).vetoed
    ballot["client"].post(PLACE, {"suggestion": str(ballot["one"].pk), "to": "unsorted", "card": "1"}, headers=HTMX)

    assert BallotRecord.objects.count() == 0


def test_the_veto_pill_turns_the_veto_off_when_it_is_on_and_on_when_it_is_off(ballot):
    def veto_to():
        return re.findall(r'"to": "([^"]+)"', bar_of(opened(ballot["client"], ballot["one"]).text))[-1]

    assert veto_to() == "veto"
    place(ballot["client"], ballot["one"], "veto")
    assert veto_to() == "unsorted"


def test_the_reason_is_saved_from_the_card_and_answered_in_its_box_alone(ballot):
    place(ballot["client"], ballot["one"], "veto")
    answer = ballot["client"].post(REASON, {"suggestion": str(ballot["one"].pk), "text": "Spiders.", "card": "1"}, headers=HTMX).text

    assert BallotRecord.objects.get().veto_reason == "Spiders."
    assert answer.lstrip().startswith('<div class="vote-reason"') and "Saved." in answer and "film-card" not in answer


def test_seen_it_is_set_from_the_card_and_the_checkbox_is_answered(ballot):
    answer = ballot["client"].post(SEEN, {"suggestion": str(ballot["one"].pk), "seen": ["0", "1"], "card": "1"}, headers=HTMX).text

    assert BallotRecord.objects.get().seen_it is True
    assert "checked" in answer and "<li" not in answer
    answer = ballot["client"].post(SEEN, {"suggestion": str(ballot["one"].pk), "seen": ["0"], "card": "1"}, headers=HTMX).text
    assert BallotRecord.objects.count() == 0 and "checked" not in answer


def test_the_vetoed_by_line_lists_the_other_vetoers_with_reasons_and_never_the_viewers_own(ballot):
    voters = ballot["voters"]
    for name, reason in (("Hanna", "spiders"), ("Dani", None)):
        other = signed_in(voters[name])
        place(other, ballot["one"], "veto")
        if reason:
            other.post(REASON, {"suggestion": str(ballot["one"].pk), "text": reason})
    place(ballot["client"], ballot["one"], "veto")

    page = opened(ballot["client"], ballot["one"]).text
    line = re.search(r'<span class="film-card__label">Vetoed by</span>(.*?)</p>', page, re.S)[1]

    assert re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", line)).strip() == "Dani, Hanna (spiders)"


def test_a_voter_who_only_scored_is_in_neither_line(ballot):
    scorer = signed_in(ballot["voters"]["Dani"])
    place(scorer, ballot["one"], 2)
    page = opened(ballot["client"], ballot["one"]).text

    assert "Vetoed by" not in page and "Seen by" not in page
    signed_in(ballot["voters"]["Hanna"]).post(SEEN, {"suggestion": str(ballot["one"].pk), "seen": "1"})
    place(signed_in(ballot["voters"]["Hanna"]), ballot["one"], "veto")
    page = opened(ballot["client"], ballot["one"]).text
    assert re.search(r"Vetoed by</span>\s*Hanna\s*</p>", page) and re.search(r"Seen by</span>\s*Hanna\s*</p>", page) and "Dani" not in page


def test_the_seen_by_line_lists_other_voters_who_have_seen_it(ballot):
    voters = ballot["voters"]
    for name in ("Hanna", "Dani", "ada"):
        signed_in(voters[name]).post(SEEN, {"suggestion": str(ballot["one"].pk), "seen": "1"})

    line = re.search(r'<span class="film-card__label">Seen by</span>(.*?)</p>', opened(ballot["client"], ballot["one"]).text, re.S)[1]

    assert line.strip() == "Dani, Hanna"


def test_each_line_is_absent_when_empty(ballot):
    page = opened(ballot["client"], ballot["one"]).text

    assert "Vetoed by" not in page and "Seen by" not in page


def test_opening_one_card_closes_the_other_in_the_same_answer(ballot):
    answer = opened(ballot["client"], ballot["one"], closes=str(ballot["two"].pk)).text

    assert f"hx-swap-oob=\"outerHTML:li[data-suggestion='{ballot['two'].pk}']\"" in answer and 'class="tile' in answer


def test_the_title_closes_a_card_to_its_tile_or_veto_row(ballot):
    assert 'class="tile' in opened(ballot["client"], ballot["one"], close="1").text
    place(ballot["client"], ballot["one"], "veto")
    assert 'class="veto-row"' in opened(ballot["client"], ballot["one"], close="1").text
    assert f'hx-get="{CARD}?suggestion={ballot["one"].pk}&amp;close=1"' in opened(ballot["client"], ballot["one"]).text


def test_a_card_for_a_film_no_longer_on_the_ballot_reloads_the_tab(ballot):
    ballot["one"].delete()
    assert opened(ballot["client"], ballot["one"]).headers.get("HX-Redirect")


def test_outside_vote_the_route_reloads_the_tab(ballot):
    walk_on_to(Phase.PICK)
    assert opened(ballot["client"], ballot["two"]).headers.get("HX-Redirect")


def test_the_viewers_own_suggestion_opens_with_no_withdraw_in_its_bar(ballot):
    own = film(ballot["ada"], "Ada's own")
    page = opened(ballot["client"], own).text

    assert "withdraw" not in page.lower()


def test_a_card_scripted_to_reload_when_its_neighbour_is_not_on_the_page():
    script = (settings.BASE_DIR / "ribcage/static/components/ballot-board.js").read_text(encoding="utf-8")

    assert re.search(r'addEventListener\("htmx:oobErrorNoTarget", reload\)', script)


def test_a_card_un_vetoed_to_the_tray_stands_where_a_reload_puts_it(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ada = voters["ada"]
    client = signed_in(ada)
    watched.set_ticked(ada, DOG, True)
    plain = [film(voters["Hanna"], f"Plain {number}") for number in range(6)]
    ringed = add(voters["Hanna"], "Ringed too", dog=(12, 1))
    ringed.approval = "approved"
    ringed.save()
    for each in [*plain, ringed]:
        place(client, each, "veto")
        answer = client.post(PLACE, {"suggestion": str(each.pk), "to": "unsorted", "card": "1"}, headers=HTMX).text
        tray = region(client.get("/").text, "unsorted")
        at = tray.index(each.pk)
        expected = f"afterend:li[data-suggestion='{tray[at - 1]}']" if at else "afterbegin:ul[data-place='unsorted']"
        assert expected in answer
        place(client, each, "veto")
        client.post(PLACE, {"suggestion": str(each.pk), "to": "unsorted"}, headers=HTMX)


def test_seen_it_sits_on_the_score_row_after_the_veto_pill(ballot):
    bar = bar_of(opened(ballot["client"], ballot["one"]).text)
    row = re.search(r'class="vote-bar__scores".*?\n  </div>', bar, re.S)[0]

    assert row.index("vote-bar__veto") < row.index('class="vote-seen"') and "Seen it" in row
    assert "Seen it" not in bar.replace(row, "")


def test_the_your_score_group_holds_the_six_pills_and_seen_it_stays_outside_it(ballot):
    tree = Tree(bar_of(opened(ballot["client"], ballot["one"]).text))
    groups = [node for node in tree.root.within() if node.attrs.get("role") == "group"]
    assert len(groups) == 1 and groups[0].attrs.get("aria-label") == "Your score"
    inside = [node.tag for node in groups[0].within()]

    assert inside.count("button") == 6 and "input" not in inside and "form" not in inside
    seen = tree.find(".vote-seen")
    assert len(seen) == 1 and groups[0] not in seen[0].up()
