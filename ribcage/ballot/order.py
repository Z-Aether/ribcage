"""The order a voter's tray and bands list their tiles in, pure over ids (#9, #38, #119)."""

from hashlib import sha256


def shuffle_key(voter_id, suggestion_id):
    # A stable digest, never Python's salted hash, so the order survives a restart (#63, #119).
    return sha256(f"{voter_id}:{suggestion_id}".encode()).digest()


def shuffled(voter_id, suggestion_ids):
    """The ids in the voter's own fixed shuffle: it depends on each id alone, so adding a film leaves the rest in their relative order."""
    return sorted(suggestion_ids, key=lambda suggestion_id: shuffle_key(voter_id, suggestion_id))


def tray_order(voter_id, suggestion_ids, matched_ids):
    """Films matching the voter's watched list first, weak matches included, then the rest; each group in the voter's shuffle (#35 §1, #38)."""
    matched = [suggestion_id for suggestion_id in suggestion_ids if suggestion_id in matched_ids]
    rest = [suggestion_id for suggestion_id in suggestion_ids if suggestion_id not in matched_ids]
    return shuffled(voter_id, matched) + shuffled(voter_id, rest)
