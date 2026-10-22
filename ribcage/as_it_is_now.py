"""Back and Forward show a voter or admin page as the server has it now, never the browser's copy (#84)."""

from django.utils.cache import patch_cache_control


def walled(request):
    """Whether the request reached a voter or admin page, read from the marks on its view, as the walls read them (#76, #84)."""
    view = getattr(request.resolver_match, "func", None)
    if view is None:
        return False
    return getattr(view, "admin_required", False) or getattr(view, "login_required", True) is not False


class NoStoreBehindTheWalls:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if walled(request):
            # The HTTP cache keeps nothing, so Back and Forward ask the server again; public pages stay cacheable (#73, #84).
            patch_cache_control(response, no_store=True)
        return response
