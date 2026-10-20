from django import template
from django.conf import settings

from ribcage.films import card, poster

register = template.Library()


@register.filter
def poster_url(film, size):
    return poster.poster_url(film, size)


@register.filter
def title_card_fill(film):
    return poster.title_card_fill(film)


@register.filter
def trimmed_note(text):
    return card.trimmed(text, settings.NOTE_TRIM_LENGTH)
