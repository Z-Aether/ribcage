import logging.config

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.test import override_settings
from django.urls import path
from django.views.decorators.http import require_GET


@login_not_required
@require_GET
def broken_page(request):
    raise RuntimeError("the page broke")


urlpatterns = [path("broken/", broken_page)]


@override_settings(ROOT_URLCONF=__name__)
def test_a_server_error_is_logged_to_stderr_with_its_traceback(client, capsys):
    # The handler binds sys.stderr when configured, so configure it again under the capture (#51).
    logging.config.dictConfig(settings.LOGGING)
    client.raise_request_exception = False

    response = client.get("/broken/", headers={"X-Forwarded-For": "203.0.113.77"})

    logged = capsys.readouterr().err
    assert response.status_code == 500
    assert "Internal Server Error: /broken/" in logged
    assert "Traceback" in logged and "RuntimeError: the page broke" in logged
    assert "203.0.113.77" not in logged
