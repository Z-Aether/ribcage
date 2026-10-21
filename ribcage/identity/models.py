from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models

from ribcage.identity import display_names


class VoterManager(BaseUserManager):
    def create_voter(self, display_name, password=None, *, password_hash=None):
        """The one way to make a voter; `password_hash` lets seed hash once (#69)."""
        display_name = display_names.clean(display_name)
        if self.filter(display_name_key=display_names.key(display_name)).exists():
            raise ValidationError("That display name is taken.", code="taken")
        voter = self.model(display_name=display_name)
        if password_hash is not None:
            voter.password = password_hash
        else:
            voter.set_password(password)
        voter.save(using=self._db)
        return voter

    def get_by_natural_key(self, display_name):
        return self.get(display_name_key=display_names.key(display_name))


class Voter(AbstractBaseUser):
    # The minimal base has no is_staff or is_superuser, so only a voter can be a row (#16, #26).
    display_name = models.CharField(max_length=display_names.MAX_LENGTH)
    # Unique regardless of case, shown as typed; casefolding can lengthen a name (#37, #69).
    display_name_key = models.CharField(max_length=display_names.MAX_LENGTH * 3, unique=True, editable=False)

    objects = VoterManager()

    USERNAME_FIELD = "display_name"

    def save(self, *args, **kwargs):
        self.display_name_key = display_names.key(self.display_name)
        if (update_fields := kwargs.get("update_fields")) is not None and "display_name" in update_fields:
            kwargs["update_fields"] = {*update_fields, "display_name_key"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name
