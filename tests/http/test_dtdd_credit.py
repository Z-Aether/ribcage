"""Every view that shows DoesTheDogDie's data carries its hyperlinked credit, as its terms require (#5, #112).

Data of DoesTheDogDie's is a record's name, a topic's label, description or keywords, or its counts. Wherever a page or fragment shows any, it sits in a region marked
`data-dtdd`, and that region holds its own credit: the footer's standing link counts for none. Seeded with sentinel strings, every page and
every card fragment is swept in each phase, so a slice not yet written fails here until it carries the credit. A fragment that swaps into a region
the page already credits is a part: its landing is held to sit in such a region instead.
"""

import re
import urllib.parse
from html.parser import HTMLParser

import pytest
from django.db import transaction
from django.test import Client
from django.urls import reverse

from ribcage.console import moves
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import correction, stored, watched
from tests.dtdd import Dtdd, detail, item
from tests.http.routes import ADMIN, FRAGMENTS, Fragment, NO_DTDD_DATA, VOTER, address, kind, pages_of, route_templates
from tests.http.signing_in import sign_in_as_the_admin
from tests.http.sweeping import CAT, DESCRIPTION, DOG, GROUP, KEYWORDS, NO, RECORD, TOPIC, YES, Answer, add, sentinel_vocabulary, sweep
from tests.http.test_phase import walk_to

CREDIT_ADDRESS = "https://www.doesthedogdie.com/"
CREDIT_WORDS = "Powered by DoesTheDogDie.com"
# The counts are bare numbers, so they are caught in any format a surface writes them in: "7771 yes", "7771/7772", "7,771" or a title (#112).
SENTINELS = (RECORD, TOPIC, GROUP, DESCRIPTION, KEYWORDS, str(YES), str(NO), f"{YES:,}", f"{NO:,}")
CASEFOLDED = tuple(sentinel.casefold() for sentinel in SENTINELS)


def carries(text):
    """Whether `text` holds a sentinel in any case: the My warnings page's search text casefolds the label and keywords (#108, #112)."""
    folded = text.casefold()
    return any(sentinel in folded for sentinel in CASEFOLDED)


# Hidden inputs that carry opaque tokens, whose random characters could spell a count.
OPAQUE = {"csrfmiddlewaretoken", "snapshot"}
LEDGER_STATUS = re.compile(r"\d+ topics?")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Regions(HTMLParser):
    """A response read for where DoesTheDogDie's data sits: in which marked region, and what credit each region holds itself."""

    def __init__(self, text):
        super().__init__()
        self.stack = []
        self.regions = [{"shown": [], "credits": 0}]
        self.anchor = None
        self.feed(text)
        self.close()

    @property
    def region(self):
        for element in reversed(self.stack):
            if element["region"] is not None:
                return element["region"]
        return None

    def shows(self, what):
        (self.region or self.regions[0])["shown"].append(what)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("name") not in OPAQUE:
            for value in attrs.values():
                if value and carries(value):
                    self.shows(value)
        if tag in VOID:
            return
        region = None
        if "data-dtdd" in attrs:
            region = {"shown": [], "credits": 0}
            self.regions.append(region)
        self.stack.append({"tag": tag, "region": region, "classes": (attrs.get("class") or "").split()})
        if tag == "a" and attrs.get("href") == CREDIT_ADDRESS:
            self.anchor = ""

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            if self.anchor.strip() == CREDIT_WORDS and self.region is not None:
                self.region["credits"] += 1
            self.anchor = None
        tags = [element["tag"] for element in self.stack]
        if tag in tags:
            del self.stack[len(tags) - tags[::-1].index(tag) - 1 :]

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor += data
        if carries(data):
            self.shows(data)
        # The ledger's DoesTheDogDie column states a count of topics, which no sentinel can mark (#102).
        elif LEDGER_STATUS.fullmatch(data.strip()) and any("films-ledger__dtdd" in element["classes"] for element in self.stack):
            self.shows(data)


def violations(text):
    """What is wrong with where a response shows DoesTheDogDie's data: shown outside any marked region, or in one with no credit of its own."""
    found = Regions(text)
    outside = [f"shown outside any region: {shown.strip()[:60]!r}" for shown in found.regions[0]["shown"]]
    uncredited = [f"a region shows {region['shown'][0].strip()[:60]!r} without its credit" for region in found.regions[1:] if region["shown"] and region["credits"] != 1]
    return outside + uncredited


def shown_anywhere(text):
    return carries(text) or any(LEDGER_STATUS.fullmatch(cell) for cell in re.findall(r'films-ledger__dtdd[^>]*>([^<]*)<', text))


# The checker itself, on pages built to be right and wrong.
CREDIT = f'<a href="{CREDIT_ADDRESS}">{CREDIT_WORDS}</a>'


def test_data_in_a_region_with_its_credit_is_held():
    assert violations(f"<section data-dtdd><p>{RECORD}</p>{CREDIT}</section>") == []


def test_data_outside_a_region_is_a_violation_whatever_credit_the_page_carries():
    assert violations(f"<section data-dtdd>{CREDIT}</section><p>{TOPIC}</p>")
    assert violations(f'<footer>{CREDIT}</footer><p title="{GROUP}">x</p>')


def test_a_region_without_its_own_credit_is_a_violation_even_when_another_region_has_one():
    assert violations(f"<section data-dtdd><p>{RECORD}</p></section><section data-dtdd>{CREDIT}</section>")
    assert violations(f"<main data-dtdd>{CREDIT}<section data-dtdd><p>{YES}/{NO}</p></section></main>")


def test_a_credit_with_other_words_or_another_address_is_no_credit():
    assert violations(f'<section data-dtdd>{RECORD}<a href="{CREDIT_ADDRESS}">DTDD</a></section>')
    assert violations(f'<section data-dtdd>{RECORD}<a href="https://example.com/">{CREDIT_WORDS}</a></section>')


def test_the_ledgers_count_of_topics_is_data_that_needs_its_region():
    cell = '<td class="films-ledger__dtdd films-ledger__dtdd--matched">2 topics</td>'
    assert violations(cell)
    assert violations(f"<div data-dtdd>{cell}{CREDIT}</div>") == []


# The built surfaces.
@pytest.fixture
def films(voters, monkeypatch):
    """Four films, one in each approval and one added by hand, holding sentinels for every record and topic, and the vocabulary; Hanna ticks the dog."""
    stored.replace_vocabulary(dtdd_client.Client("key", Dtdd(vocabulary=sentinel_vocabulary())).vocabulary().value)
    ada = voters["ada"]
    made = [add(ada, "Undecided", Approval.UNDECIDED), add(ada, "Approved", Approval.APPROVED), add(ada, "Dropped", Approval.DROPPED), add(ada, "By hand", Approval.UNDECIDED, counted=False)]
    watched.set_ticked(voters["Hanna"], DOG, True)
    # The preview's record, which the correction fetches from DoesTheDogDie: its name is a sentinel too (#105).
    previewed = Dtdd(details=[detail(item(9001, f"{RECORD}previewed", 2002), (DOG, YES, NO), (CAT, YES, NO))])
    monkeypatch.setattr(correction, "dtdd_client", lambda: dtdd_client.Client("key", previewed))
    return made


@pytest.fixture
def viewers(voters):
    voter = Client()
    voter.force_login(voters["Hanna"])
    admin = Client()
    sign_in_as_the_admin(admin)
    return {VOTER: voter, ADMIN: admin}


def held(sweeping):
    return [(answer.where, problem) for answer in sweeping if not answer.part for problem in violations(answer.text)]


# A part swaps inside a region of its host page, which is read as a tree to find where each swap lands (#112).
class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children = tag, attrs, parent, []
        self.credits = 0
        self.region = self if "data-dtdd" in attrs else (parent.region if parent else None)

    def within(self):
        yield self
        for child in self.children:
            yield from child.within()

    def up(self):
        node = self
        while node is not None:
            yield node
            node = node.parent

    def matches(self, selector):
        if selector.startswith("#"):
            return self.attrs.get("id") == selector[1:]
        if selector.startswith("."):
            return selector[1:] in (self.attrs.get("class") or "").split()
        if selector.startswith("["):
            return selector.strip("[]") in self.attrs
        return self.tag == selector

    def root(self):
        return list(self.up())[-1]

    def inherited(self, name):
        return next((node.attrs[name] for node in self.up() if name in node.attrs), None)

    @property
    def credited(self):
        """Whether the swap lands inside a region of DoesTheDogDie's data that holds its own credit."""
        return self.region is not None and self.region.credits == 1


class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.root = Node("#root", {}, None)
        self.open = self.root
        self.anchor = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {name: value or "" for name, value in attrs}, self.open)
        self.open.children.append(node)
        if tag not in VOID:
            self.open = node
        if tag == "a" and node.attrs.get("href") == CREDIT_ADDRESS:
            self.anchor = [node, ""]

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            node, words = self.anchor
            if words.strip() == CREDIT_WORDS and node.region is not None:
                node.region.credits += 1
            self.anchor = None
        node = self.open
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.open = node.parent

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor[1] += data

    def find(self, selector):
        return [node for node in self.root.within() if node.matches(selector)]


def target_of(node):
    """The element a request from `node` swaps into, or None where it swaps nothing in; htmx's own target syntax, as far as the app uses it."""
    swap = (node.inherited("hx-swap") or "").split()
    if swap[:1] == ["none"]:
        return None
    target = node.inherited("hx-target")
    if target is None or target == "this":
        return node
    word, _, selector = target.partition(" ")
    if word == "closest":
        found = next((each for each in node.up() if each.matches(selector)), None)
    elif word == "find":
        found = next((each for each in node.within() if each is not node and each.matches(selector)), None)
    elif word in {"next", "previous", "body", "window", "document"}:
        raise AssertionError(f"hx-target {target!r} is not read by this test; teach it")
    else:
        found = next((each for each in node.root().within() if each.matches(target)), None)
    assert found is not None, f"hx-target {target!r} finds nothing from <{node.tag}>"
    return found


def landings(part, hosts):
    """Where a part's answer lands in each host page whose elements fetch it: the problems found, and how many elements fetch it."""
    route = reverse(part.fragment.route)
    oob = [node.attrs.get("id") for node in Tree(part.text).root.within() if "hx-swap-oob" in node.attrs]
    problems, fetchers = [], 0
    for host in hosts:
        tree = Tree(host.text)
        asking = [node for node in tree.root.within() if urllib.parse.urlsplit(node.attrs.get("hx-get") or node.attrs.get("hx-post") or "").path == route]
        fetchers += len(asking)
        for node in asking:
            target = target_of(node)
            if target is not None and not target.credited:
                problems.append(f"{part.fragment.route} swaps into <{target.tag}> of {host.where}, outside a credited region")
        for oob_id in oob if asking else []:
            landed = tree.find(f"#{oob_id}")
            if not landed or not all(node.credited for node in landed):
                problems.append(f"{part.fragment.route} swaps #{oob_id} out of band into {host.where}, outside a credited region")
    return problems, fetchers


def part_problems(answers):
    """What is wrong with where each part lands, and the routes of the parts that landed anywhere."""
    hosts = [answer for answer in answers if not answer.part]
    problems, landed = [], set()
    for part in answers:
        if part.part:
            found, fetchers = landings(part, hosts)
            problems += found
            if fetchers:
                landed.add(part.fragment.route)
    return problems, landed


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.VOTE, Phase.PICK])
def test_every_page_and_card_fragment_shows_doesthedogdies_data_only_in_a_region_with_its_credit(viewers, films, phase):
    walk_to(phase)
    answers = list(sweep(viewers, films))

    assert held(answers) == []
    assert part_problems(answers)[0] == []


def test_every_listed_answer_shows_data_somewhere_and_every_part_lands_somewhere(viewers, films):
    """A listed answer that shows nothing in any phase checks nothing: its parameters have gone stale, or it was written wrongly (#112)."""
    shown, landed = set(), set()
    for phase in (Phase.SUGGEST, Phase.APPROVE, Phase.VOTE, Phase.PICK):
        # Each phase is swept from a fresh pool: the sweep's own match saves would otherwise change what the next one meets.
        with transaction.atomic():
            walk_to(phase)
            answers = list(sweep(viewers, films))
            transaction.set_rollback(True)
        shown |= {index for answer in answers if answer.fragment is not None and shown_anywhere(answer.text) for index, each in enumerate(FRAGMENTS) if each is answer.fragment}
        landed |= part_problems(answers)[1]

    expected = {index for index, each in enumerate(FRAGMENTS) if not each.part and each.route not in NO_DTDD_DATA}
    assert [FRAGMENTS[index] for index in sorted(expected - shown)] == []
    assert {each.route for each in FRAGMENTS if each.part} - landed == set()


def test_the_sweep_meets_the_card_the_warnings_page_and_the_ledger_as_regions_that_hold_data(viewers, films):
    answers = {answer.where: answer.text for answer in sweep(viewers, films)}

    def holding(where):
        return [region for region in Regions(answers[where]).regions[1:] if region["shown"]]

    assert [region["credits"] for region in holding(f"{VOTER} /")] == [1, 1, 1]
    assert [region["credits"] for region in holding(f"{VOTER} /warnings/")] == [1]
    # The ledger's own region, then its three cards' sections under it.
    assert [region["credits"] for region in holding(f"{ADMIN} /console/films/")] == [1, 1, 1, 1]


def test_in_run_no_page_or_fragment_holds_any_of_it(viewers, films):
    walk_to(Phase.PICK)
    assert any(shown_anywhere(answer.text) for answer in sweep(viewers, films))
    moves.make(Phase.PICK, Phase.RUN)

    answers = list(sweep(viewers, films))

    assert [answer.where for answer in answers if shown_anywhere(answer.text)] == []


def unclassified(viewers):
    """The voter and admin routes that are no swept page and are listed in neither FRAGMENTS nor NO_DTDD_DATA."""
    swept = {(template, entry.name) for kind_of in (VOTER, ADMIN) for template, entry in pages_of(kind_of)}
    listed = {fragment.route for fragment in FRAGMENTS} | NO_DTDD_DATA
    left = []
    for template, entry in route_templates():
        route_kind = kind(entry)
        if route_kind not in {VOTER, ADMIN} and route_kind is not None:
            continue
        if entry.name in listed:
            continue
        # A page that answers 405 or redirects on its plain GET is no page the sweep reads.
        if (template, entry.name) in swept and viewers[route_kind or ADMIN].get(address(template)).status_code == 200:
            continue
        left.append(entry.name)
    return left


def test_every_voter_and_admin_route_is_a_swept_page_a_listed_fragment_or_known_to_hold_none(viewers, films):
    names = {entry.name for _, entry in route_templates()}
    listed = {fragment.route for fragment in FRAGMENTS}

    assert listed <= names and NO_DTDD_DATA <= names
    assert unclassified(viewers) == []
    assert {fragment.viewer for fragment in FRAGMENTS} == {VOTER, ADMIN}


def test_counts_descriptions_and_keywords_are_data_in_whatever_format_they_are_written():
    for shown in (f"{YES}/{NO}", f"{YES:,} yes", f"{NO} no"):
        assert violations(f"<p>{shown}</p>"), shown
    assert violations(f'<p title="{YES}/{NO}">x</p>')
    assert violations(f'<button title="{DESCRIPTION}1">x</button>')
    assert violations(f'<li data-search="{KEYWORDS}1">x</li>')
    # What search_text writes: the label and keywords casefolded (#112).
    assert violations(f'<li data-search="{TOPIC.casefold()} {KEYWORDS.casefold()}1">x</li>')


def hosted(host, route, text):
    """The problems and fetchers found for a part answering `text` to `route`, over one host page."""
    part = Answer("part", Fragment(route, VOTER, "GET", {}, True), text)
    return landings(part, [Answer("host", None, host)])


def test_a_part_that_lands_in_a_credited_region_is_held_and_one_that_lands_elsewhere_is_not():
    inside = f'<section data-dtdd><details hx-get="/dtdd/?suggestion=1" hx-target="find .wait"><p class="wait"></p></details>{CREDIT}</section>'
    assert hosted(inside, "dtdd_topics", "<ul></ul>") == ([], 1)
    outside = f'<section data-dtdd>{CREDIT}</section><details hx-get="/dtdd/" hx-target="find .wait"><p class="wait"></p></details>'
    assert hosted(outside, "dtdd_topics", "<ul></ul>")[0]
    uncredited = '<section data-dtdd><details hx-get="/dtdd/" hx-target="find .wait"><p class="wait"></p></details></section>'
    assert hosted(uncredited, "dtdd_topics", "<ul></ul>")[0]


def test_a_part_swapped_out_of_band_names_ids_that_sit_in_a_credited_region_of_its_host():
    ask = '<form hx-post="/warnings/tick/" hx-swap="none"></form>'
    answer = '<p id="here" hx-swap-oob="true">x</p>'
    assert hosted(f'<div data-dtdd><p id="here"></p>{ask}{CREDIT}</div>', "warnings_tick", answer) == ([], 1)
    assert hosted(f'<div data-dtdd>{ask}{CREDIT}</div><p id="here"></p>', "warnings_tick", answer)[0]
    assert hosted(f'<div data-dtdd>{ask}{CREDIT}</div>', "warnings_tick", answer)[0]
