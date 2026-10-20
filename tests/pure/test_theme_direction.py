import pytest
from django.test import RequestFactory

from ribcage.gallery.directions import COOKIE, DEFAULT_DIRECTION, chosen_direction


def a_request(query, cookie):
    request = RequestFactory().get(f"/{query}")
    if cookie:
        request.COOKIES[COOKIE] = cookie
    return request


@pytest.mark.parametrize(
    ("query", "cookie", "direction"),
    [
        ("", None, DEFAULT_DIRECTION),
        ("?direction=b", None, "b"),
        ("", "c", "c"),
        ("?direction=b", "c", "b"),
        ("?direction=z", "nonsense", DEFAULT_DIRECTION),
    ],
)
def test_a_link_picks_the_direction_before_the_remembered_one(query, cookie, direction):
    assert chosen_direction(a_request(query, cookie)) == direction
