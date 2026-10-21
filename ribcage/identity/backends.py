from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend


class DisplayNameBackend(BaseBackend):
    """Signs a voter in by display name without regard to case, so a phone's capital letter can't fail (#69)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        Voter = get_user_model()
        username = username or kwargs.get(Voter.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            voter = Voter.objects.get_by_natural_key(username)
        except Voter.DoesNotExist:
            # Hash anyway, so a missing name takes as long as a wrong password (#16, #69).
            Voter().set_password(password)
            return None
        return voter if voter.check_password(password) else None

    def get_user(self, user_id):
        return get_user_model().objects.filter(pk=user_id).first()
