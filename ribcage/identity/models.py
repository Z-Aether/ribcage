from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Voter(AbstractBaseUser):
    # The minimal base has no is_staff or is_superuser, so only a voter can be a row (#16, #26).
    display_name = models.CharField(max_length=20, unique=True)

    objects = BaseUserManager()

    USERNAME_FIELD = "display_name"

    def __str__(self):
        return self.display_name
