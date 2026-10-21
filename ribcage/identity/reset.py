"""Reset: the admin giving a voter who lost their password a generated one, which they must change at their next login (#28, #80)."""

import secrets

from django.db import transaction
from django.utils.crypto import constant_time_compare, salted_hmac

from ribcage.identity.models import Voter

# No 0, o, 1, l or i, so a password read off one screen and typed on a phone can't be mistyped by sight (#80).
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
GROUPS = 4
GROUP_LENGTH = 4


def generated_password():
    # Four groups of four from 31 characters, about 79 bits; Django's checks never see it (#37).
    return "-".join("".join(secrets.choice(ALPHABET) for _ in range(GROUP_LENGTH)) for _ in range(GROUPS))


def replacing(voter):
    """Names the password a reset will replace, so the confirm posted again by a reload resets nothing (#80)."""
    return salted_hmac("ribcage.identity.reset", voter.password, algorithm="sha256").hexdigest()


def reset(voter, replaced):
    """The voter's new password, or None when they are gone or their password is no longer the one `replaced` names."""
    # The new hash fails each session's auth hash, so every session of theirs ends at its next request, with no rows to delete (#37, #80).
    with transaction.atomic():
        voter = Voter.objects.filter(pk=voter.pk).first()
        if voter is None or not constant_time_compare(replacing(voter), replaced or ""):
            return None
        password = generated_password()
        voter.set_password(password)
        voter.must_change_password = True
        voter.save(update_fields=["password", "must_change_password"])
    return password
