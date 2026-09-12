"""Synthetic controls only; no private thesis data in tests."""
import copy
from fractions import Fraction
import unittest
from correct_midrank_distinct_metadata import corrected_metadata, exact_midranks, tree_changes


def fixture():
    raw = [{"Supplier_ID": str(i), "Strength_Exact_or_High_Precision": f"{i}/1",
            "Normalized_Betweenness_Exact_or_High_Precision": f"{2-i}/2"} for i in range(3)]
    run = {"run_id": "R00", "network_spec_id": "N00", "transformation": "midrank_percentile",
        "requested_embeddedness_weights": [0.5, 0.5], "remove_indicator": None,
        "zero_variance": {"Strength": False, "Normalized_Betweenness": False},
        "effective_weights": {"Embeddedness": {"Strength": 0.5, "Normalized_Betweenness": 0.5}},
        "dimension_summary": {"Embeddedness": {"distinct_n": 2, "median": 50.0}},
        "thresholds": {"Embeddedness": {"low": 50.0, "high": 50.0}},
        "supplier_rows": [{"Supplier_ID": str(i), "Strength_Transformed": float(50*i),
            "Betweenness_Transformed": float(100-50*i), "Embeddedness_Score": 50.0,
            "Profile": "unchanged synthetic label"} for i in range(3)]}
    return {"networks": {"N00": {"supplier_rows": raw}}, "primary": copy.deepcopy(run), "sensitivity_runs": [run]}


class MidrankMetadataTests(unittest.TestCase):
    def test_rational_tied_midranks(self):
        self.assertEqual(exact_midranks({"a": 1, "b": 1, "c": 2}),
                         {"a": Fraction(25), "b": Fraction(25), "c": Fraction(100)})
        self.assertIsNone(exact_midranks({"a": 2, "b": 2}))
        self.assertIsNone(exact_midranks({"a": 2}))

    def test_primary_duplicate_and_full_tree_guard(self):
        original = fixture(); snapshot = copy.deepcopy(original)
        successor, receipt = corrected_metadata(original, {"R00"})
        self.assertEqual(original, snapshot)
        self.assertEqual(len(receipt["corrections"]), 2)
        self.assertEqual(successor["primary"]["dimension_summary"]["Embeddedness"]["distinct_n"], 1)
        self.assertEqual(tree_changes(original, successor), receipt["corrections"])
        self.assertTrue(all(change["path"][-1] == "distinct_n" for change in receipt["corrections"]))

    def test_idempotent(self):
        first, _ = corrected_metadata(fixture(), {"R00"})
        second, receipt = corrected_metadata(first, {"R00"})
        self.assertEqual(first, second)
        self.assertEqual(receipt["corrections"], [])

    def test_nonmidrank_skipped(self):
        data = fixture()
        data["primary"]["transformation"] = "log1p_minmax"
        data["sensitivity_runs"][0]["transformation"] = "log1p_minmax"
        successor, receipt = corrected_metadata(data, {"R00"})
        self.assertEqual(data, successor)
        self.assertEqual(len(receipt["skipped_records"]), 2)

    def test_bad_display_fails_closed(self):
        data = fixture(); data["primary"]["supplier_rows"][0]["Embeddedness_Score"] = 49.0
        with self.assertRaises(ValueError): corrected_metadata(data, {"R00"})

    def test_bad_transformed_indicator_fails_closed(self):
        data = fixture(); data["primary"]["supplier_rows"][0]["Strength_Transformed"] = 1.0
        with self.assertRaises(ValueError): corrected_metadata(data, {"R00"})

    def test_unknown_run_fails_closed(self):
        with self.assertRaises(ValueError): corrected_metadata(fixture(), {"UNKNOWN"})

    def test_unequal_rational_weights(self):
        data = fixture()
        for run in [data["primary"], data["sensitivity_runs"][0]]:
            run["requested_embeddedness_weights"] = [0.6, 0.4]
            run["effective_weights"]["Embeddedness"] = {"Strength": 0.6, "Normalized_Betweenness": 0.4}
            for i, row in enumerate(run["supplier_rows"]): row["Embeddedness_Score"] = float(40 + 10*i)
        successor, _ = corrected_metadata(data, {"R00"})
        self.assertEqual(successor["primary"]["dimension_summary"]["Embeddedness"]["distinct_n"], 3)

    def test_removed_indicator_renormalizes(self):
        data = fixture()
        for run in [data["primary"], data["sensitivity_runs"][0]]:
            run["remove_indicator"] = "Normalized_Betweenness"
            run["effective_weights"]["Embeddedness"] = {"Strength": 1.0}
            for i, row in enumerate(run["supplier_rows"]): row["Embeddedness_Score"] = float(50*i)
        successor, _ = corrected_metadata(data, {"R00"})
        self.assertEqual(successor["primary"]["dimension_summary"]["Embeddedness"]["distinct_n"], 3)

    def test_constant_indicator_renormalizes(self):
        data = fixture()
        for row in data["networks"]["N00"]["supplier_rows"]:
            row["Normalized_Betweenness_Exact_or_High_Precision"] = "0/1"
        for run in [data["primary"], data["sensitivity_runs"][0]]:
            run["zero_variance"]["Normalized_Betweenness"] = True
            run["effective_weights"]["Embeddedness"] = {"Strength": 1.0}
            for i, row in enumerate(run["supplier_rows"]):
                row["Betweenness_Transformed"] = None
                row["Embeddedness_Score"] = float(50*i)
        successor, _ = corrected_metadata(data, {"R00"})
        self.assertEqual(successor["primary"]["dimension_summary"]["Embeddedness"]["distinct_n"], 3)

    def test_no_usable_indicators(self):
        data = fixture()
        for row in data["networks"]["N00"]["supplier_rows"]:
            row["Strength_Exact_or_High_Precision"] = "0/1"
            row["Normalized_Betweenness_Exact_or_High_Precision"] = "0/1"
        for run in [data["primary"], data["sensitivity_runs"][0]]:
            run["zero_variance"] = {"Strength": True, "Normalized_Betweenness": True}
            run["effective_weights"]["Embeddedness"] = {}
            for row in run["supplier_rows"]:
                row["Strength_Transformed"] = row["Betweenness_Transformed"] = row["Embeddedness_Score"] = None
        successor, _ = corrected_metadata(data, {"R00"})
        self.assertEqual(successor["primary"]["dimension_summary"]["Embeddedness"]["distinct_n"], 0)

    def test_tree_guard_detects_nonmetadata_difference(self):
        before = fixture(); after = copy.deepcopy(before)
        after["primary"]["supplier_rows"][0]["Profile"] = "wrong"
        self.assertEqual(tree_changes(before, after)[0]["path"][-1], "Profile")


if __name__ == "__main__":
    unittest.main()
