"""Apply explicit source findings to a successor ledger, preserving provenance.

This pure helper verifies preimages and allowed changes, not source truth.
Actual review receipts and evidence stay in the ignored local workspace.
"""
from copy import deepcopy
from hashlib import sha256
import json

ALLOWED = {
    'Analytical_Technology_EN', 'BMW_Relationship_Supported_Revised',
    'BMW_Relationship_Status', 'BMW_Evidence_IDs',
    'Exact_BMW_Technology_Revised', 'Exact_BMW_Technology_Status',
    'Exact_Evidence_IDs', 'Decision_Reason', 'Capability_Decision_Reason',
    'BMW_Relationship_Decision_Reason', 'Exact_BMW_Technology_Decision_Reason',
    'Source_Recheck_Status', 'Source_Recheck_Date', 'Review_Status',
}


def fingerprint(row):
    return sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':')).encode()).hexdigest()


def apply_reviewed_corrections(rows, package):
    original = {row['Link_ID']: row for row in rows}
    if len(original) != len(rows):
        raise ValueError('Original Link_ID values must be unique')
    if any('Source_Supplier_ID' in row or 'Finalisation_Source_Review' in row for row in rows):
        raise ValueError('Already revised ledger; review the successor explicitly')
    updated = deepcopy(rows)
    by_id = {row['Link_ID']: row for row in updated}
    for row in updated:
        row['Source_Supplier_ID'] = row['Supplier_ID']
    touched = set()
    allowed_by_id = {}
    for correction in package['corrections']:
        key = correction['Link_ID']
        if key in touched:
            raise ValueError('Duplicate correction ID')
        touched.add(key)
        before = original[key]
        if fingerprint(before) != correction['expected_row_sha256']:
            raise ValueError(f'{key}: source row changed')
        changes = correction['changes']
        if not changes or not set(changes) <= ALLOWED:
            raise ValueError('Correction changes a protected or unknown field')
        if not correction.get('evidence_receipts') or not correction.get('reason'):
            raise ValueError('Correction requires inspectable evidence and reason')
        by_id[key].update(deepcopy(changes))
        by_id[key]['Finalisation_Source_Review'] = deepcopy(correction)
        allowed_by_id[key] = set(changes)
    aliases = package['supplier_aliases']
    from_ids = [item['from_id'] for item in aliases]
    targets = [item['to_id'] for item in aliases]
    if len(set(from_ids)) != len(from_ids) or set(from_ids) & set(targets):
        raise ValueError('Duplicate, chained or cyclic supplier aliases are forbidden')
    all_suppliers = {row['Supplier_ID'] for row in rows}
    for alias in aliases:
        if alias['from_id'] == alias['to_id'] or alias['to_id'] not in all_suppliers:
            raise ValueError('Alias target must be a different existing supplier')
        members = [row for row in updated if row['Source_Supplier_ID'] == alias['from_id']]
        if not members or sorted(row['Link_ID'] for row in members) != sorted(alias['expected_link_ids']):
            raise ValueError('Alias membership changed; re-review all affected rows')
        if not alias.get('reason') or not alias.get('evidence_receipts'):
            raise ValueError('Supplier alias requires reviewed entity-scope evidence')
        for row in members:
            if fingerprint(original[row['Link_ID']]) != alias['expected_rows'][row['Link_ID']]:
                raise ValueError('Alias source row changed')
            row['Supplier_ID'] = alias['to_id']
            audit = row.setdefault('Finalisation_Source_Review', {})
            audit['supplier_alias'] = deepcopy(alias)
            allowed_by_id.setdefault(row['Link_ID'], set()).add('Supplier_ID')
    for row in updated:
        key = row['Link_ID']
        if row['Exact_BMW_Technology_Revised'] and not (
            row['Capability_Supported_Revised'] and row['BMW_Relationship_Supported_Revised']
            and row['Identity_Resolved_Revised'] and row['Exact_Evidence_IDs']
        ):
            raise ValueError('Exact support lacks its constituent evidence decisions')
        if not row['BMW_Relationship_Supported_Revised'] and row['BMW_Evidence_IDs']:
            raise ValueError('Unsupported relationship retains positive evidence IDs')
        restored = {k: v for k, v in row.items()
                    if k not in ('Source_Supplier_ID', 'Finalisation_Source_Review')}
        for field in allowed_by_id.get(key, set()):
            if field in original[key]:
                restored[field] = original[key][field]
            else:
                restored.pop(field, None)
        if restored != original[key]:
            raise AssertionError('Unapproved field changed')
    return updated
