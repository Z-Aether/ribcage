"""The whole tab onto a page: how a refused post is answered, as a plain form post or as htmx (#76, #78)."""

from django.http import HttpResponse
from django.shortcuts import redirect


def reload_the_tab(request, page):
    """Send the tab onto `page`: a redirect for a plain post, an `HX-Redirect` for htmx (#76, #78)."""
    if request.headers.get("HX-Request") == "true":
        # HX-Redirect rather than HX-Refresh, so an htmx post lands on the same page a plain post does (#78).
        return HttpResponse(headers={"HX-Redirect": page})
    return redirect(page)
