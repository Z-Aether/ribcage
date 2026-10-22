from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction

from ribcage.identity import display_names


class VoterManager(BaseUserManager):
    def create_voter(self, display_name, password=None, *, password_hash=None):
        """The one way to make a voter; `password_hash` lets seed hash once (#69)."""
        voter = self.model(display_name=display_names.clean(display_name))
        if password_hash is not None:
            voter.password = password_hash
        else:
            voter.set_password(password)
        try:
            # The unique key alone decides, so two registrations racing for one name can't both pass a check (#69).
            with transaction.atomic(using=self._db):
                voter.save(using=self._db)
        except IntegrityError:
            raise ValidationError("That display name is taken.", code="taken") from None
        return voter

    def get_by_natural_key(self, display_name):
        return self.get(display_name_key=display_names.key(display_name))


class Voter(AbstractBaseUser):
    # The minimal base has no is_staff or is_superuser, so only a voter can be a row (#16, #26).
    display_name = models.CharField(max_length=display_names.MAX_LENGTH)
    # Unique regardless of case, shown as typed; casefolding can lengthen a name (#37, #69).
    display_name_key = models.CharField(max_length=display_names.MAX_LENGTH * 3, unique=True, editable=False)
    # Set by the admin's reset and cleared by the voter's own change, which until then is the only page they reach (#28, #80).
    must_change_password = models.BooleanField(default=False)

    objects = VoterManager()

    USERNAME_FIELD = "display_name"

    def save(self, *args, **kwargs):
        self.display_name_key = display_names.key(self.display_name)
        if (update_fields := kwargs.get("update_fields")) is not None and "display_name" in update_fields:
            kwargs["update_fields"] = {*update_fields, "display_name_key"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class LoginFailure(models.Model):
    """One failed login, counted by `backoff`; a model rather than the cache table, which `migrate` never makes (#71)."""

    key = models.TextField(db_index=True)
    at = models.DateTimeField()
