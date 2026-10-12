import pytest

DATABASE_FIXTURES = {"db", "transactional_db", "django_db_setup", "live_server"}
REFUSAL = "A pure test never touches the database (#25). Put it in tests/http instead."


def refuse_unblocking():
    pytest.fail(REFUSAL)


@pytest.fixture(autouse=True)
def _pure_tests_never_reach_the_database(request, django_db_blocker, monkeypatch):
    # pytest-django blocks unmarked access; this also refuses its opt-outs (#25).
    if request.node.get_closest_marker("django_db") or DATABASE_FIXTURES & set(request.fixturenames):
        pytest.fail(REFUSAL)
    # Every test's closure holds django_db_blocker through pytest-django's autouse fixtures, so refuse its use instead.
    monkeypatch.setattr(django_db_blocker, "unblock", refuse_unblocking)
