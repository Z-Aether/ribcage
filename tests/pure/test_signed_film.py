"""A film carried signed through the pitch step's form, read back by Add exactly as TMDB gave it (#61, #93)."""

import pytest
from django.core import signing

from ribcage.films import signed
from ribcage.films.film import RuntimeSource
from tests.films import CABINET_OF_CURIOSITIES, INFESTED, THE_SHINING


@pytest.mark.parametrize("film", [THE_SHINING, INFESTED, CABINET_OF_CURIOSITIES], ids=["the shining", "no poster", "by hand"])
def test_a_signed_film_reads_back_exactly_as_it_was_signed(film):
    assert signed.unsigned(signed.signed(film)) == film


def test_the_runtime_source_reads_back_as_its_enum():
    assert signed.unsigned(signed.signed(THE_SHINING)).runtime_source is RuntimeSource.TMDB


def a_tampered(value):
    # A character of the payload changed, as a voter editing the field would.
    middle = len(value) // 3
    return value[:middle] + ("A" if value[middle] != "A" else "B") + value[middle + 1 :]


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(a_tampered(signed.signed(THE_SHINING)), id="altered"),
        pytest.param(signed.signed(THE_SHINING)[:-3], id="cut short"),
        pytest.param("", id="empty"),
        pytest.param("not signed at all", id="unsigned"),
        pytest.param(signing.dumps({"title": "The Shining"}), id="signed for something else"),
    ],
)
def test_anything_but_a_film_signed_here_is_tampered(value):
    with pytest.raises(signed.Tampered):
        signed.unsigned(value)
