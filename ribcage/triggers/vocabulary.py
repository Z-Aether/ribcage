"""DoesTheDogDie's vocabulary: its topics, labelled and grouped as DoesTheDogDie does (#23, #101)."""

from dataclasses import dataclass, replace

from ribcage.triggers.dtdd import a_string, an_int, an_int_or_none


@dataclass(frozen=True)
class SuperCategory:
    super_category_id: int | None
    name: str


# Where a topic goes when its category or super-category doesn't resolve, after every real one, DoesTheDogDie's own "Other" among them, so it takes another name (#101).
UNCATEGORIZED = SuperCategory(None, "Uncategorized")


@dataclass(frozen=True)
class Topic:
    topic_id: int
    # DoesTheDogDie's minimalName, the label used everywhere; its name and notName are rendered nowhere (#23).
    label: str
    keywords: str
    description: str
    super_category: SuperCategory


@dataclass(frozen=True)
class Vocabulary:
    topics: tuple[Topic, ...]
    super_categories: tuple[SuperCategory, ...]

    @property
    def groups(self):
        """Each super-category with its topics, in DoesTheDogDie's order, Uncategorized last, and none left empty."""
        groups = [(group, [topic for topic in self.topics if topic.super_category == group]) for group in (*self.super_categories, UNCATEGORIZED)]
        return [(group, topics) for group, topics in groups if topics]

    def topic(self, topic_id):
        return next((topic for topic in self.topics if topic.topic_id == topic_id), None)


def a_list(answer):
    if not isinstance(answer, list):
        raise ValueError("Each vocabulary list is an array.")
    return answer


def text(value):
    return "" if value is None else a_string(value).strip()


def super_categories_from(answer):
    return tuple(SuperCategory(an_int(each["id"]), a_string(each["name"])) for each in a_list(answer))


def categories_from(answer):
    """Each category's super-category id; a topic reaches its category only for that, since its name is rendered nowhere (#23)."""
    return {an_int(each["id"]): an_int_or_none(each.get("topicSuperCategoryId")) for each in a_list(answer)}


def topics_from(answer):
    """Each topic, with its category id still to resolve."""
    return [
        (
            Topic(
                topic_id=an_int(each["id"]),
                label=a_string(each["minimalName"]),
                keywords=text(each.get("keywords")),
                description=text(each.get("description")),
                super_category=UNCATEGORIZED,
            ),
            an_int_or_none(each.get("topicCategoryId")),
        )
        for each in a_list(answer)
    ]


def assembled(topics, categories, super_categories):
    """`topics_from`, `categories_from` and `super_categories_from` put together, unresolved topics under Uncategorized."""
    by_id = {group.super_category_id: group for group in super_categories}
    return Vocabulary(
        topics=tuple(
            replace(topic, super_category=by_id.get(categories.get(category_id), UNCATEGORIZED)) for topic, category_id in topics
        ),
        super_categories=super_categories,
    )
