"""The My warnings page's data: the vocabulary in DoesTheDogDie's grouping, with a voter's ticks marked (#23, #107)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    topic_id: int
    label: str
    description: str
    ticked: bool


@dataclass(frozen=True)
class Section:
    # The id of the section's element, which the in-place swaps and a plain post's return address name (#107).
    anchor: str
    name: str
    rows: tuple[Row, ...]

    @property
    def ticked(self):
        return sum(row.ticked for row in self.rows)


@dataclass(frozen=True)
class Page:
    sections: tuple[Section, ...]

    @property
    def chips(self):
        """The ticked rows as the page lists them, alphabetical across sections; a retired topic is not in the vocabulary, so none shows (#107)."""
        return tuple(sorted((row for section in self.sections for row in section.rows if row.ticked), key=sort_key))

    def section_of(self, topic_id):
        return next((section for section in self.sections if any(row.topic_id == topic_id for row in section.rows)), None)


def sort_key(row):
    return (row.label.casefold(), row.topic_id)


def anchor_of(group):
    return f"group-{'uncategorized' if group.super_category_id is None else group.super_category_id}"


def page(vocabulary, ticked_ids):
    """Every super-category in DoesTheDogDie's order as a section, its topics flat and alphabetical by label (#23)."""
    return Page(
        tuple(
            Section(
                anchor_of(group),
                group.name,
                tuple(sorted((Row(topic.topic_id, topic.label, topic.description, topic.topic_id in ticked_ids) for topic in topics), key=sort_key)),
            )
            for group, topics in vocabulary.groups
        )
    )
