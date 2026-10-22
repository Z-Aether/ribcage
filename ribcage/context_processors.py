from django.conf import settings


def footer(request):
    return {"abuse_email": settings.ABUSE_EMAIL}
