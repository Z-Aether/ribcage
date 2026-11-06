"""The tuning harness's mapping of a ranking onto the scale, its title matching and its clean skip without `private/` (#174)."""

from ribcage.films.corpus import CorpusEntry
from tests import tuning


def test_a_ranking_falls_into_five_even_bands_from_plus_three_to_minus_one():
    scored = tuning.scores_from_ranking({film: film + 1 for film in range(10)})
    assert [scored[film][0] for film in range(10)] == [3, 3, 2, 2, 1, 1, 0, 0, -1, -1]
    assert not any(vetoed for _, vetoed in scored.values())


def test_a_blank_is_left_unsorted_and_does_not_take_a_place():
    scored = tuning.scores_from_ranking({"a": 1, "b": None, "c": 2})
    assert "b" not in scored
    assert (scored["a"][0], scored["c"][0]) == (3, 1)


def test_an_x_is_a_veto_and_takes_no_place_in_the_bands():
    scored = tuning.scores_from_ranking({"a": 1, "b": "X", "c": 2})
    assert scored["b"] == (None, True)
    assert scored["a"][0] == 3


def test_tied_ranks_share_a_band():
    scored = tuning.scores_from_ranking({"a": 1, "b": 1, "c": 1, "d": 4, "e": 5})
    assert scored["a"] == scored["b"] == scored["c"]


def test_a_ranking_of_one_film_scores_it_the_top():
    assert tuning.scores_from_ranking({"a": 1}) == {"a": (3, False)}


ENTRIES = [CorpusEntry("The Thing", 1982, 1), CorpusEntry("Cube", 1997, 2), CorpusEntry("Cube", 2002, 3)]


def test_a_title_matches_by_year_then_by_a_title_only_one_entry_has():
    assert tuning.match_title("Cube (2002)", ENTRIES) == 2
    assert tuning.match_title("the thing (1981)", ENTRIES) == 0
    assert tuning.match_title("Cube", ENTRIES) is None
    assert tuning.match_title("Nothing (2000)", ENTRIES) is None


def test_a_file_becomes_an_instance_leaving_out_the_unmatched(tmp_path):
    (tmp_path / "votes_1.csv").write_text("film,x,y\nThe Thing (1982),1,2\nUnknown (2000),2,1\nCube (1997),,X\n", encoding="utf-8")
    [found] = tuning.past_instances(tmp_path, ([*ENTRIES], {0: 109, 1: 90, 2: 95}, {}))
    assert found.name == "A" and found.voters == ("A1", "A2")
    assert {film for _, film, _, _, _ in found.records} == {0, 1}
    assert ("A2", 1, None, True, False) in found.records
    assert not any(voter == "A1" and film == 1 for voter, film, *_ in found.records)


def test_the_harness_skips_cleanly_without_the_directory(tmp_path):
    assert tuning.past_instances(tmp_path / "missing", ([], {}, {})) == []


def test_the_summary_names_each_rule_and_each_instance_by_letter_with_its_worst_and_median():
    rows = [
        {"instance": letter, "rule": rule, "k": 2, "budget": 8, "knob": "none", "answer": "open", "solve_ms": ms, "render_ms": ms, "slates": 1, "stopped": False}
        for letter, rule, ms in [("A", "total", 100), ("A", "total", 300), ("B", "total", 200), ("A", "leximin", 4000), ("B", "leximin", 500)]
    ]
    said = []

    tuning.summarise(rows, said.append)

    assert any(line.startswith("leximin k=2: 2 answers, worst render 4000 ms (A,") and line.endswith("over 3 s: 1") for line in said)
    assert "  A: median 300 ms, worst 300 ms" in said and "  B: median 500 ms, worst 500 ms" in said
    assert any(line.startswith("total k=2: 3 answers, worst render 300 ms") for line in said)
