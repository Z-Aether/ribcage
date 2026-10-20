from django.conf import settings

# The theme directions on trial in #58's rounds. The pick deletes the losers, this module and the switch (#58).
DIRECTIONS = {
    "a": "Neon orange",
    "b": "Pumpkin and aubergine",
    "c": "Peat and bone",
}
DEFAULT_DIRECTION = "a"
QUERY_PARAMETER = "direction"
COOKIE = "theme_direction"


def chosen_direction(request):
    for value in (request.GET.get(QUERY_PARAMETER), request.COOKIES.get(COOKIE)):
        if value in DIRECTIONS:
            return value
    return DEFAULT_DIRECTION


def theme_direction(request):
    return {
        "theme_direction": chosen_direction(request),
        "theme_directions": DIRECTIONS,
        "theme_direction_switch": settings.DEBUG,
    }
