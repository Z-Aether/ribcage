"""Correcting a film's runtime for the copy the group will watch: positive whole minutes, refused gently, never coerced (#21, #90)."""

import re

# The most a PositiveSmallIntegerField holds on every database Django supports.
LONGEST = 32767

# Worded without naming an act, so the pencil, the pitch step's Add and the Films tab's box share them (#93).
EMPTY = "The runtime is empty. Type its length in minutes, like 144."
NOT_WHOLE_MINUTES = "A runtime is whole minutes, like 144. Type it that way."
NOT_POSITIVE = "A runtime is at least a minute long. Check the number."
TOO_LONG = "No copy runs that long. Check the number."


class Refused(ValueError):
    """A runtime that isn't positive whole minutes, carrying what to tell the voter."""


def minutes(typed):
    """The runtime typed, in whole minutes, or Refused with a gentle word for anything else (#90)."""
    text = typed.strip()
    if not text:
        raise Refused(EMPTY)
    if re.fullmatch(r"-[0-9]+", text):
        raise Refused(NOT_POSITIVE)
    if not re.fullmatch(r"[0-9]+", text):
        raise Refused(NOT_WHOLE_MINUTES)
    # Counted before it is read, so a pasted run of digits never meets int's own limit on their number.
    digits = text.lstrip("0")
    if len(digits) > len(str(LONGEST)) or int(digits or 0) > LONGEST:
        raise Refused(TOO_LONG)
    if not digits:
        raise Refused(NOT_POSITIVE)
    return int(digits)


def correct(suggestion, typed):
    """Set the suggestion's runtime as typed. TMDB's stays as fetched, so the card reads the new one as by hand (#21)."""
    suggestion.runtime = minutes(typed)
    # A filtered update, so a suggestion withdrawn since it was read changes nothing rather than raising (#97).
    type(suggestion).objects.filter(pk=suggestion.pk).update(runtime=suggestion.runtime)
