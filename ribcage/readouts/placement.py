"""The one rule for a ballot record being placed, over plain data (#119, #146)."""


def is_placed(record):
    """A record with a score or a veto, as (score, vetoed, ...); a record holding only seen-it is not (#119)."""
    return record is not None and (record[0] is not None or record[1])
