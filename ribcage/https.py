from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed


class EveryRequestIsHttps:
    # The proxy forces HTTPS, so outside DEBUG every request arrived over HTTPS, whatever the proxy forwards (#31, #54).
    def __init__(self, get_response):
        if settings.DEBUG:
            raise MiddlewareNotUsed
        self.get_response = get_response

    def __call__(self, request):
        request.META["wsgi.url_scheme"] = "https"
        return self.get_response(request)
