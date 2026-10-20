from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from ribcage.gallery import samples


def gallery(request):
    # A dev-only visual reference: it never exists on the deployment, which never sets DEBUG (#58).
    if not settings.DEBUG:
        raise Http404
    return render(request, "gallery/gallery.html", samples.gallery())
