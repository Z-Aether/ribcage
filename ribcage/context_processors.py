from django.conf import settings

from ribcage.as_it_is_now import walled


def marathon_name(request):
    return {"marathon_name": settings.MARATHON_NAME}


def footer(request):
    return {"abuse_email": settings.ABUSE_EMAIL}


def as_it_is_now(request):
    return {"walled_page": walled(request)}
