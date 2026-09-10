import copy
import unittest

from evidence_holds import apply_holds, record_digest


class EvidenceHoldTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "Link_ID": "SYNTHETIC-1", "Supplier_ID": "SYNTHETIC-SUPPLIER",
            "Capability_Supported_Revised": 1, "Primary_Eligible": 1,
            "Exact_BMW_Technology_Revised": 0, "BMW_Relationship_Supported_Revised": 0,
            "Non_Excluded_Revised": 1, "Capability_Evidence_IDs": ["SYNTHETIC-EVD"],
            "Issue_Tags": [], "Original_Capability_Flag": 1,
            "Frozen_Publication_Dates": {"SYNTHETIC-EVD": "unknown"},
        }
        self.hold = {
            "Link_ID": self.row["Link_ID"], "expected_record_sha256": record_digest(self.row),
            "reason": "Synthetic source does not establish the exact process.",
            "source_url": "https://example.org/synthetic", "source_locator": "Synthetic section",
            "search_scope": "Synthetic fixture only", "candidate_label": "Synthetic held process",
        }

    def test_hold_is_traceable_and_preserves_inputs(self):
        original = copy.deepcopy(self.row)
        result = apply_holds([self.row], [self.hold], "2026-09-10")[0]
        self.assertEqual(self.row, original)
        self.assertEqual(result["Primary_Eligible"], 0)
        self.assertEqual(result["Capability_Supported_Revised"], 0)
        self.assertEqual(result["Capability_Evidence_IDs"], [])
        for key in ("Supplier_ID", "Non_Excluded_Revised", "Original_Capability_Flag", "Frozen_Publication_Dates"):
            self.assertEqual(result[key], original[key])
        audit = result["Finalisation_Evidence_Hold"]
        self.assertFalse(audit["student_review_confirmed"])
        self.assertEqual(audit["previous_capability_evidence_ids"], ["SYNTHETIC-EVD"])
        reconstructed = {k: v for k, v in result.items() if k != "Finalisation_Evidence_Hold"}
        for key, delta in audit["changes"].items():
            if key in original:
                reconstructed[key] = delta["before"]
            else:
                reconstructed.pop(key)
        self.assertEqual(reconstructed, original)

    def test_rejects_stale_review(self):
        self.row["Source_Recheck_Date"] = "changed"
        with self.assertRaisesRegex(ValueError, "Stale"):
            apply_holds([self.row], [self.hold], "2026-09-10")

    def test_rejects_relationship_scope_change(self):
        self.row["BMW_Relationship_Supported_Revised"] = 1
        self.hold["expected_record_sha256"] = record_digest(self.row)
        with self.assertRaisesRegex(ValueError, "joint review"):
            apply_holds([self.row], [self.hold], "2026-09-10")

    def test_rejects_duplicate_hold(self):
        with self.assertRaisesRegex(ValueError, "Duplicate hold"):
            apply_holds([self.row], [self.hold, self.hold], "2026-09-10")

    def test_rejects_missing_evidence(self):
        self.hold["source_locator"] = ""
        with self.assertRaisesRegex(ValueError, "Missing review evidence"):
            apply_holds([self.row], [self.hold], "2026-09-10")


if __name__ == "__main__":
    unittest.main()
