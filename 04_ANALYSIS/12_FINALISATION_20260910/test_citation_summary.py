"""Synthetic review records only; none are thesis source approvals."""
import copy
import unittest
from citation_summary import citation_summary, validate_summary, SUPPORTED, PENDING


class CitationSummary(unittest.TestCase):
    def setUp(self):
        self.rows = [
            dict(reference_id='A', current_support_status=SUPPORTED),
            dict(reference_id='A', current_support_status=PENDING),
            dict(reference_id='B', current_support_status=SUPPORTED),
        ]

    def test_counts_uses_not_unique_sources(self):
        result = citation_summary(self.rows)
        self.assertEqual(result['all_recognised_occurrences'], 3)
        self.assertEqual(result['unique_cited_sources'], 2)
        self.assertEqual(result['counts'], {'A': 2, 'B': 1})

    def test_partial_source_appears_in_both_sets(self):
        result = citation_summary(self.rows)
        self.assertEqual(result['checked_sources'], ['A', 'B'])
        self.assertEqual(result['remaining_sources'], ['A'])
        self.assertEqual(result['pending_references'], 1)

    def test_legacy_aliases_agree(self):
        result = citation_summary(self.rows)
        self.assertEqual(result['supported_uses'], result['supported_occurrences'])
        self.assertEqual(result['pending_uses'], result['pending_occurrences'])
        self.assertEqual(result['remaining_occurrences'], result['pending_occurrences'])
        self.assertEqual(validate_summary(result, self.rows), result)

    def test_stale_secondary_counter_is_rejected(self):
        result = citation_summary(self.rows)
        result['supported_occurrences'] = 1
        with self.assertRaisesRegex(ValueError, 'supported_occurrences'):
            validate_summary(result, self.rows)

    def test_missing_or_stale_source_set_is_rejected(self):
        for key, value in [('remaining_sources', []), ('checked_sources', ['B'])]:
            result = citation_summary(self.rows)
            result[key] = value
            with self.assertRaisesRegex(ValueError, key):
                validate_summary(result, self.rows)
        result = citation_summary(self.rows)
        del result['pending_uses']
        with self.assertRaisesRegex(ValueError, 'pending_uses'):
            validate_summary(result, self.rows)

    def test_bad_status_or_reference_is_not_silently_ignored(self):
        for row in [dict(reference_id='A', current_support_status='maybe'),
                    dict(reference_id='', current_support_status=SUPPORTED)]:
            with self.assertRaises(ValueError):
                citation_summary([row])

    def test_empty_input_is_explicit_and_inputs_are_preserved(self):
        original = copy.deepcopy(self.rows)
        citation_summary(self.rows)
        self.assertEqual(self.rows, original)
        result = citation_summary([])
        self.assertEqual(result['all_recognised_occurrences'], 0)
        self.assertEqual(result['remaining_sources'], [])
        self.assertEqual(result['counts'], {})


if __name__ == '__main__':
    unittest.main()
