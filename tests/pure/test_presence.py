"""Presence strips and shared time: a pure function of the vetoes on the timetable's films and their start order (#149)."""

from ribcage.readouts.presence import Hole, Showing, presence

# Four films of 100 minutes with a 10 minute gap between, and a Dinner between the second and third.
A = Showing("a", 0, 100, True)
B = Showing("b", 110, 210, True)
DINNER = Showing("dinner", 210, 260, False)
C = Showing("c", 270, 370, True)
D = Showing("d", 380, 480, True)


def vetoed(box, *voters):
    return Showing(box.key, box.start, box.end, box.is_film, frozenset(voters))


def test_a_voter_with_no_vetoes_on_the_timetable_is_present_throughout():
    found = presence(["ann", "bo"], [A, B, DINNER, C, D])
    assert found.strips == ()
    assert found.throughout == 2


def test_leading_and_trailing_vetoed_films_set_arrival_and_departure():
    found = presence(["ann"], [vetoed(A, "ann"), vetoed(B, "ann"), C, vetoed(D, "ann")])
    (strip,) = found.strips
    assert (strip.arrive, strip.leave, strip.holes) == (210, 380, ())
    assert found.throughout == 0


def test_a_voter_who_vetoed_only_the_first_arrives_at_its_end_and_with_none_leading_at_the_evenings_start():
    first = presence(["ann"], [vetoed(A, "ann"), B]).strips[0]
    last = presence(["ann"], [A, vetoed(B, "ann")]).strips[0]
    assert (first.arrive, first.leave) == (100, 210)
    assert (last.arrive, last.leave) == (0, 110)


def test_a_mid_evening_veto_is_a_hole():
    (strip,) = presence(["ann"], [A, vetoed(B, "ann"), DINNER, C]).strips
    assert (strip.arrive, strip.leave) == (0, 370)
    assert strip.holes == (Hole("b", 110, 210),)


def test_a_labelled_box_is_ignored_for_order_but_counts_for_the_evenings_span():
    # Dinner between the vetoed film and the next is no film: the veto still leads.
    (lead,) = presence(["ann"], [vetoed(A, "ann"), Showing("break", 100, 150, False), B]).strips
    assert lead.arrive == 100
    # A trailing labelled box extends the evening, so a voter with no trailing veto leaves at its end.
    (stays,) = presence(["ann"], [vetoed(A, "ann"), B, DINNER]).strips
    assert stays.leave == 260


def test_a_labelled_box_between_vetoed_films_does_not_end_the_run_or_make_a_hole():
    # [vetoed A, Dinner, vetoed B, C]: A and B are one leading run, so ann arrives at B's end with no hole.
    (lead,) = presence(["ann"], [vetoed(A, "ann"), Showing("dinner", 100, 110, False), vetoed(B, "ann"), Showing("c", 220, 320, True)]).strips
    assert (lead.arrive, lead.holes) == (210, ())
    # Mirror at the evening's end: [C, vetoed A, Dinner, vetoed B] leaves at A's start with no hole.
    c = Showing("c", 0, 100, True)
    a, dinner, b = Showing("a", 110, 210, True, frozenset({"ann"})), Showing("dinner", 210, 220, False), Showing("b", 220, 320, True, frozenset({"ann"}))
    (trail,) = presence(["ann"], [c, a, dinner, b]).strips
    assert (trail.leave, trail.holes) == (110, ())


def test_films_starting_together_keep_the_boxes_own_order():
    one, two = Showing("one", 0, 100, True, frozenset({"ann"})), Showing("two", 0, 100, True)
    (strip,) = presence(["ann"], [one, two]).strips
    assert (strip.arrive, strip.holes) == (100, ())


def test_a_voter_who_vetoed_every_film_has_an_empty_strip_and_there_is_no_shared_time():
    found = presence(["ann", "bo"], [vetoed(A, "ann"), vetoed(B, "ann")])
    (strip,) = found.strips
    assert strip.empty
    assert strip.arrive == strip.leave == 210
    assert found.shared == 0


def test_shared_time_is_the_span_every_strip_covers_less_the_holes_once_each():
    # ann steps out for B and leaves before D; bo arrives after A and steps out for C.
    found = presence(["ann", "bo"], [vetoed(A, "bo"), vetoed(B, "ann"), vetoed(C, "bo"), vetoed(D, "ann")])
    ann, bo = found.strips
    assert (ann.arrive, ann.leave) == (0, 380)
    assert (bo.arrive, bo.leave) == (100, 480)
    # 100..380 less B (110..210) and C (270..370).
    assert found.shared_pieces == ((100, 110), (210, 270), (370, 380))
    assert found.shared == 10 + 60 + 10


def test_holes_that_share_minutes_are_subtracted_once():
    overlapping = Showing("c", 150, 250, True, frozenset({"bo"}))
    found = presence(["ann", "bo"], [A, vetoed(B, "ann"), overlapping, Showing("d", 300, 400, True)])
    assert found.shared_pieces == ((0, 110), (250, 400))
    assert found.shared == 110 + 150


def test_with_no_strips_shared_time_is_the_whole_elapsed_time():
    found = presence(["ann"], [A, DINNER, D])
    assert found.shared == 480
    assert found.shared_pieces == ((0, 480),)


def test_a_strip_that_never_overlaps_another_leaves_no_shared_time():
    found = presence(["ann", "bo"], [vetoed(A, "bo"), vetoed(B, "ann", "bo"), vetoed(C, "ann")])
    assert found.shared == 0


def test_no_boxes_has_no_strips_and_no_time():
    found = presence(["ann"], [])
    assert (found.strips, found.throughout, found.shared) == ((), 1, 0)
