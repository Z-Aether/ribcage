from pathlib import Path
from xml.etree import ElementTree

GUARD = Path(__file__).with_name("conftest.py").read_text()
REPO_ROOT = Path(__file__).parents[2]
PURE_TESTS_REACHING_FOR_THE_DATABASE = """
def test_requests_the_database(db):
    pass


def test_unblocks_the_database(django_db_blocker):
    with django_db_blocker.unblock():
        pass
"""


def refused_tests(report):
    return {
        case.get("name")
        for case in ElementTree.parse(report).iter("testcase")
        for outcome in case
        if outcome.tag in ("failure", "error") and "A pure test never touches the database" in outcome.get("message")
    }


def test_the_guard_refuses_each_way_a_pure_test_reaches_for_the_database(pytester, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "ribcage.settings")
    pytester.makeconftest(GUARD)
    pytester.makepyfile(PURE_TESTS_REACHING_FOR_THE_DATABASE)
    report = pytester.path / "report.xml"

    # One subprocess for both cases: each run costs seconds of Django startup.
    pytester.runpytest_subprocess(f"--junitxml={report}")

    assert refused_tests(report) == {"test_requests_the_database", "test_unblocks_the_database"}
