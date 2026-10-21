from django.conf import settings


def footer(request):
    # From the environment, so the address stays out of the public repo (#73).
    return {"abuse_email": settings.ABUSE_EMAIL}
