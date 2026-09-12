import unittest
from copy import deepcopy
from apply_reviewed_corrections import apply_reviewed_corrections, fingerprint


def fixture():
    rows = [dict(Link_ID=key, Supplier_ID=supplier, Canonical_Link_ID=key,
                 Capability_Supported_Revised=1, BMW_Relationship_Supported_Revised=1,
                 BMW_Evidence_IDs=['E-' + key], Exact_BMW_Technology_Revised=0,
                 Exact_Evidence_IDs=[], Identity_Resolved_Revised=1, Primary_Eligible=1)
            for key, supplier in [('A', 'S1'), ('B', 'S2')]]
    package = dict(corrections=[], supplier_aliases=[])
    return rows, package


class ReviewedCorrectionTests(unittest.TestCase):
    def test_identity_alias_retains_claims_and_raw_keys(self):
        rows, package = fixture()
        before = deepcopy(rows)
        package['supplier_aliases'] = [dict(from_id='S1', to_id='S2', expected_link_ids=['A'],
            expected_rows={'A': fingerprint(rows[0])}, reason='Same documented unit', evidence_receipts=['review.json'])]
        result = apply_reviewed_corrections(rows, package)
        self.assertEqual(rows, before)
        self.assertEqual([r['Supplier_ID'] for r in result], ['S2', 'S2'])
        self.assertEqual([r['Source_Supplier_ID'] for r in result], ['S1', 'S2'])
        self.assertEqual([r['Canonical_Link_ID'] for r in result], ['A', 'B'])
        with self.assertRaises(ValueError):
            apply_reviewed_corrections(result, package)

    def correction(self, rows, changes):
        return dict(Link_ID='A', expected_row_sha256=fingerprint(rows[0]), changes=changes,
                    reason='Reviewed source decision', evidence_receipts=['review.json'])

    def test_relation_retraction_does_not_remove_capability(self):
        rows, package = fixture()
        package['corrections'] = [self.correction(rows, dict(BMW_Relationship_Supported_Revised=0, BMW_Evidence_IDs=[]))]
        result = apply_reviewed_corrections(rows, package)
        self.assertEqual(result[0]['Primary_Eligible'], 1)
        self.assertEqual(result[0]['Capability_Supported_Revised'], 1)
        self.assertEqual(result[0]['BMW_Relationship_Supported_Revised'], 0)

    def test_protected_primary_flag_rejected(self):
        rows, package = fixture()
        package['corrections'] = [self.correction(rows, dict(Primary_Eligible=0))]
        with self.assertRaises(ValueError):
            apply_reviewed_corrections(rows, package)

    def test_changed_preimage_rejected(self):
        rows, package = fixture()
        package['corrections'] = [self.correction(rows, dict(Decision_Reason='Corrected'))]
        rows[0]['Primary_Eligible'] = 0
        with self.assertRaises(ValueError):
            apply_reviewed_corrections(rows, package)

    def test_exact_requires_evidence_and_relationship(self):
        rows, package = fixture()
        package['corrections'] = [self.correction(rows, dict(Exact_BMW_Technology_Revised=1))]
        with self.assertRaises(ValueError):
            apply_reviewed_corrections(rows, package)

    def test_alias_missing_member_rejected(self):
        rows, package = fixture()
        package['supplier_aliases'] = [dict(from_id='S1', to_id='S2', expected_link_ids=[])]
        with self.assertRaises(ValueError):
            apply_reviewed_corrections(rows, package)


if __name__ == '__main__':
    unittest.main()
