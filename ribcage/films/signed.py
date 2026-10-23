"""A film carried through a form signed, so the post that adds it fetches nothing and no voter can alter it (#61, #93)."""

from dataclasses import asdict

from django.core import signing

from ribcage.films.film import Film, RuntimeSource

SALT = "ribcage.films.signed"


class Tampered(ValueError):
    """A signed film whose signature doesn't hold: altered, cut short, or never signed here."""


def signed(film):
    return signing.dumps(asdict(film), salt=SALT, compress=True)


def unsigned(value):
    """The film exactly as it was signed, or Tampered. It never expires: an abandoned pick costs only its fetch (#93)."""
    try:
        fields = signing.loads(value, salt=SALT)
    except signing.BadSignature:
        raise Tampered from None
    return Film(**fields | {"directors": tuple(fields["directors"]), "runtime_source": RuntimeSource(fields["runtime_source"])})
