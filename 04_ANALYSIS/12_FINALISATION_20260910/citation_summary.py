"""Consistent citation-review counts; these checks do not verify source meaning."""
from collections import Counter

SUPPORTED = 'supported_for_stated_bounded_use'
PENDING = 'pending_source_check'


def citation_summary(occurrences):
    """Derive current totals and overlapping source sets from individual uses.

    Keep legacy aliases consistent for existing audit consumers. A reference
    can have both supported and pending uses; never clear all uses by source ID.
    """
    counts = Counter()
    states = Counter()
    supported_sources, pending_sources = set(), set()
    for occurrence in occurrences:
        rid = occurrence['reference_id']
        status = occurrence['current_support_status']
        if not isinstance(rid, str) or not rid.strip():
            raise ValueError('Each citation use needs a nonempty reference ID')
        if status not in (SUPPORTED, PENDING):
            raise ValueError(f'Unrecognised citation support status: {status!r}')
        counts[rid] += 1
        states[status] += 1
        (supported_sources if status == SUPPORTED else pending_sources).add(rid)
    done, pending = states[SUPPORTED], states[PENDING]
    return {
        'all_recognised_occurrences': done + pending,
        'supported_occurrences': done,
        'pending_occurrences': pending,
        'remaining_occurrences': pending,
        'supported_uses': done,
        'pending_uses': pending,
        'unique_cited_sources': len(counts),
        'pending_references': len(pending_sources),
        'counts': dict(sorted(counts.items())),
        'checked_sources': sorted(supported_sources),
        'remaining_sources': sorted(pending_sources),
    }


def validate_summary(record, occurrences):
    """Fail when any required current summary field is missing or stale."""
    expected = citation_summary(occurrences)
    mismatches = [key for key, value in expected.items()
                  if key not in record or record[key] != value]
    if mismatches:
        raise ValueError('Citation summary differs from occurrence records: ' + ', '.join(mismatches))
    return expected
