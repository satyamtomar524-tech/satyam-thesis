"""Synthetic regression cases; none of these fixtures are thesis observations."""
import unittest
import math
from datetime import date
from fractions import Fraction

from date_sensitivity import analyse, date_class, describe_network, publication_interval


class PublicationDates(unittest.TestCase):
    start, end = date(2016, 1, 1), date(2026, 8, 25)

    def test_precision_and_cutoff(self):
        expected = {"2016": "wholly_within_window", "2025": "wholly_within_window",
                    "2026": "interval_crosses_boundary", "2026-08": "interval_crosses_boundary",
                    "2026-07": "wholly_within_window", "2026-08-25": "wholly_within_window",
                    "2026-08-26": "outside_window", "2015": "outside_window",
                    "unknown": "unknown_or_invalid", "2024-02-30": "unknown_or_invalid",
                    "2024-13": "unknown_or_invalid"}
        for value, classification in expected.items():
            with self.subTest(value=value):
                self.assertEqual(date_class(value, self.start, self.end), classification)

    def test_event_date_not_publication(self):
        self.assertEqual(date_class("2022-01-01", self.start, self.end, True),
                         "event_or_related_item_date_not_publication")

    def test_leap_month(self):
        self.assertEqual(publication_interval("2024-02"), (date(2024, 2, 1), date(2024, 2, 29)))


class NetworkAndEligibility(unittest.TestCase):
    @staticmethod
    def row(link, supplier, category, evidence):
        return {"Link_ID": link, "Canonical_Link_ID": link, "Supplier_ID": supplier,
                "Analytical_Taxonomy_ID": category, "Origin": "synthetic",
                "Primary_Eligible": 1, "Capability_Evidence_IDs": evidence}

    def test_two_sources_do_not_double_count(self):
        row = self.row("L1", "S1", "T1", ["E1", "E2"])
        result = analyse([row], [{"Evidence_ID": "E1", "Published_Date": "2020"},
                                 {"Evidence_ID": "E2", "Published_Date": "unknown"}],
                         date(2016, 1, 1), date(2026, 8, 25))
        self.assertEqual(result["recorded_date_restricted"]["claims"], 1)
        self.assertIsNone(result["recorded_date_restricted"]["density"])

    def test_unknown_is_not_zero_or_dated(self):
        row = self.row("L1", "S1", "T1", ["E1"])
        result = analyse([row], [{"Evidence_ID": "E1", "Published_Date": "unknown"}],
                         date(2016, 1, 1), date(2026, 8, 25))
        self.assertEqual(result["recorded_date_restricted"]["claims"], 0)
        self.assertIsNone(result["recorded_date_restricted"]["density"])

    def test_overlap_topology_and_isolate(self):
        rows = [self.row("L1", "S1", "T1", []), self.row("L2", "S2", "T1", []),
                self.row("L3", "S3", "T2", []), self.row("L4", "S1", "T1", [])]
        result = describe_network(rows)
        self.assertEqual(result["positive_overlap_pairs"], 1)
        self.assertEqual(result["memberships"], 3)
        self.assertEqual(result["component_sizes"], [2, 1])
        self.assertEqual(result["isolates"], 1)
        self.assertEqual(result["density"], 1 / 3)

    def test_duplicate_claim_rejected(self):
        row = self.row("L1", "S1", "T1", [])
        with self.assertRaises(ValueError):
            describe_network([row, row])

    def test_missing_evidence_rejected(self):
        with self.assertRaises(KeyError):
            analyse([self.row("L1", "S1", "T1", ["missing"])], [],
                    date(2016, 1, 1), date(2026, 8, 25))


class ManuscriptWorkedExample(unittest.TestCase):
    def test_three_supplier_illustration(self):
        vectors = {"A": (2, 1), "B": (1, 1), "C": (0, 1)}
        expected = {("A", "B"): Fraction(2, 3), ("A", "C"): Fraction(1, 3),
                    ("B", "C"): Fraction(1, 2)}
        strength = {supplier: Fraction(0) for supplier in vectors}
        for (a, b), expected_similarity in expected.items():
            similarity = Fraction(sum(min(x, y) for x, y in zip(vectors[a], vectors[b])),
                                  sum(max(x, y) for x, y in zip(vectors[a], vectors[b])))
            self.assertEqual(similarity, expected_similarity)
            strength[a] += similarity
            strength[b] += similarity
        self.assertEqual(strength, {"A": Fraction(1), "B": Fraction(7, 6), "C": Fraction(5, 6)})
        self.assertAlmostEqual(-sum(p * math.log(p) for p in (2 / 3, 1 / 3)) / math.log(2),
                               0.9182958340544896)
        # All direct lengths are shorter than the route through the third node.
        self.assertLess(Fraction(3, 2), Fraction(3) + Fraction(2))
        self.assertLess(Fraction(3), Fraction(3, 2) + Fraction(2))
        self.assertLess(Fraction(2), Fraction(3, 2) + Fraction(3))
        breadth_pct, evenness_pct = [75, 75, 0], [50, 100, 0]
        self.assertEqual([(a + b) / 2 for a, b in zip(breadth_pct, evenness_pct)], [62.5, 87.5, 0])


if __name__ == "__main__":
    unittest.main()
