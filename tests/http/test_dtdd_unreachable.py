"""DoesTheDogDie is unreachable here, so a test that reaches it gives the client a fake transport (#25, #101)."""

import pytest

from ribcage.triggers import client
from ribcage.triggers.client import NotAnswering


def test_the_network_transport_refuses_and_the_client_reads_that_as_not_answering(settings):
    settings.DEBUG = False

    with pytest.raises(ConnectionError, match="give it a fake transport"):
        client.over_the_network("/items/8740", {}, {})
    with pytest.raises(NotAnswering, match="/items/8740"):
        client.dtdd_client().record(8740)


def test_a_fake_transport_answers_in_its_place(monkeypatch):
    listed = {"id": 8740, "name": "Arachnophobia", "releaseYear": 1990, "itemTypeName": "Movie", "topicItemStats": []}
    monkeypatch.setattr(client, "over_the_network", lambda path, parameters, headers: (listed, {}))

    assert client.dtdd_client().record(8740).value.record.name == "Arachnophobia"
