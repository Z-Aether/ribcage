"""DoesTheDogDie's vocabulary: three lists read into topics under their super-category (#23, #101)."""

import pytest

from ribcage.triggers.client import Client, NotAnswering
from ribcage.triggers.vocabulary import UNCATEGORIZED, SuperCategory, Topic

KEY = "dtdd-key-that-must-not-leak"

TOPICS = [
    {
        "id": 153,
        "name": "a dog dies",
        "notName": "no dogs die",
        "keywords": "dog death, pet",
        "description": "A dog dies on screen.\r\n",
        "doesName": "Does the dog die",
        "listName": "where a dog dies",
        "minimalName": "dog death",
        "topicCategoryId": 1,
        "altTopicCategoryId": None,
    },
    {
        "id": 264,
        "name": "a baby is stillborn",
        "notName": "no babies are stillborn",
        "keywords": "stillbirth",
        "description": "The birth of a dead baby.",
        "minimalName": "stillbirths",
        "topicCategoryId": 2,
        "altTopicCategoryId": None,
    },
    {"id": 400, "name": "a new one", "keywords": "", "description": "", "minimalName": "new ones", "topicCategoryId": 99},
    {"id": 402, "name": "a thing", "keywords": "", "description": "", "minimalName": "other things", "topicCategoryId": 4},
    {"id": 401, "name": "an orphan", "keywords": None, "description": None, "minimalName": "orphans", "topicCategoryId": 3},
]
CATEGORIES = [
    {"id": 1, "name": "Animal death", "topicSuperCategoryId": 54},
    {"id": 2, "name": "Pregnancy", "topicSuperCategoryId": 53},
    {"id": 3, "name": "Unfiled", "topicSuperCategoryId": 77},
    {"id": 4, "name": "Misc", "topicSuperCategoryId": 60},
]
SUPER_CATEGORIES = [
    {"id": 54, "name": "Animals", "shortName": "Animals"},
    {"id": 53, "name": "Children & Babies", "shortName": "Kids"},
    {"id": 50, "name": "Violence", "shortName": "Violence"},
    {"id": 60, "name": "Other", "shortName": "Other"},
]
ANSWERS = {"/topics": TOPICS, "/topiccategories": CATEGORIES, "/topicsupercategories": SUPER_CATEGORIES}


class Dtdd:
    def __init__(self, answers=ANSWERS, remaining="25"):
        self.answers = answers
        self.remaining = remaining
        self.paths = []

    def __call__(self, path, parameters, headers):
        self.paths.append(path)
        return self.answers[path], {"x-ratelimit-remaining-minute": self.remaining}


ANIMALS = SuperCategory(54, "Animals")
KIDS = SuperCategory(53, "Children & Babies")
DTDD_OTHER = SuperCategory(60, "Other")


def test_the_vocabulary_is_three_calls_each_the_whole_list():
    dtdd = Dtdd()

    answer = Client(KEY, dtdd).vocabulary()

    assert sorted(dtdd.paths) == ["/topiccategories", "/topics", "/topicsupercategories"]
    assert answer.remaining == 25


def test_each_topic_reads_its_minimal_name_keywords_description_and_super_category():
    vocabulary = Client(KEY, Dtdd()).vocabulary().value

    assert vocabulary.topics[0] == Topic(
        topic_id=153, label="dog death", keywords="dog death, pet", description="A dog dies on screen.", super_category=ANIMALS
    )


def test_a_topic_whose_category_or_super_category_does_not_resolve_is_grouped_last_under_uncategorized_apart_from_dtdds_own_other():
    vocabulary = Client(KEY, Dtdd()).vocabulary().value

    assert [(group, [topic.label for topic in topics]) for group, topics in vocabulary.groups] == [
        (ANIMALS, ["dog death"]),
        (KIDS, ["stillbirths"]),
        (DTDD_OTHER, ["other things"]),
        (UNCATEGORIZED, ["new ones", "orphans"]),
    ]
    assert UNCATEGORIZED.name == "Uncategorized"


def test_a_topic_is_found_by_its_id():
    vocabulary = Client(KEY, Dtdd()).vocabulary().value

    assert vocabulary.topic(264).label == "stillbirths"
    assert vocabulary.topic(999) is None


@pytest.mark.parametrize(
    "broken",
    [
        {**ANSWERS, "/topics": {"topics": TOPICS}},
        {**ANSWERS, "/topics": [{"id": 153, "name": "a dog dies"}]},
        {**ANSWERS, "/topiccategories": [{"id": "1"}]},
        {**ANSWERS, "/topicsupercategories": [{"id": 54}]},
    ],
)
def test_a_malformed_list_raises_not_answering(broken):
    with pytest.raises(NotAnswering):
        Client(KEY, Dtdd(answers=broken)).vocabulary()
