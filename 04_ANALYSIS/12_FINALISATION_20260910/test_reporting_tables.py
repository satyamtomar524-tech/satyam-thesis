import unittest
from reporting_tables import evidence_views, agreement_label, percent


class ReportingTests(unittest.TestCase):
    def rows(self):
        return [dict(Canonical_Link_ID=str(i), Canonical_Representative=1,
                     Primary_Eligible=int(i < 2), Analytical_Taxonomy_ID="T1",
                     Capability_Supported_Revised=a, BMW_Relationship_Supported_Revised=b,
                     Exact_BMW_Technology_Revised=0)
                for i, (a, b) in enumerate([(1, 1), (1, 0), (0, 1), (0, 0)])]

    def test_independent_partition_and_different_denominators(self):
        v = evidence_views(self.rows(), {"T1": {"category": "Synthetic"}})
        self.assertEqual(v["partition"], [1, 1, 1, 1])
        self.assertEqual((v["canonical_n"], v["primary_n"], v["capability_n"], v["bmw_n"]), (4, 2, 2, 2))

    def test_alias_preserved_but_not_counted_twice(self):
        rows = self.rows()
        rows.append(dict(rows[0], Canonical_Representative=0, Primary_Eligible=0))
        v = evidence_views(rows, {"T1": {"category": "Synthetic"}})
        self.assertEqual((v["candidate_n"], v["canonical_n"]), (5, 4))

    def test_invalid_primary_alias_rejected(self):
        rows = self.rows()
        rows[0]["Canonical_Representative"] = 0
        with self.assertRaises(ValueError):
            evidence_views(rows, {"T1": {"category": "Synthetic"}})

    def test_undeclared_taxonomy_rejected(self):
        with self.assertRaises(ValueError):
            evidence_views(self.rows(), {})

    def test_diagnostic_does_not_become_full_agreement(self):
        r = {"stability": {"profile_comparison_n": 0, "diagnostic_subset_same_profile_rate": 1}}
        self.assertEqual(agreement_label(r), "Not estimable")

    def test_empty_denominator_is_not_zero_percent(self):
        self.assertEqual(percent(0, 0), "Not estimable")

    def test_comparable_denominator(self):
        r = {"stability": {"profile_comparison_n": 4, "same_profile_n": 3, "common_supplier_n": 5}}
        self.assertEqual(agreement_label(r), "3/4 (75.00%)")


if __name__ == "__main__":
    unittest.main()
