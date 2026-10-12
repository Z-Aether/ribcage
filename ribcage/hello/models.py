from django.db import models, transaction

KEPT_MESSAGES = 20
MAX_MESSAGE_LENGTH = 200


class Message(models.Model):
    text = models.CharField(max_length=MAX_MESSAGE_LENGTH)

    @classmethod
    def newest_first(cls):
        return cls.objects.order_by("-pk")

    def save(self, *args, **kwargs):
        # Trimming on every save keeps a stranger on the public page from filling the disk (#47).
        with transaction.atomic():
            super().save(*args, **kwargs)
            kept = list(Message.newest_first().values_list("pk", flat=True)[:KEPT_MESSAGES])
            Message.objects.exclude(pk__in=kept).delete()
