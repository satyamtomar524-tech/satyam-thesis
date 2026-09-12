"""Synthetic safe-output and semantic-digest tests; no thesis observations loaded."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from recalculate_finalisation import argument_parser, code_dependencies, resolve_output, semantic_json_digest


class RecalculationCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.here = Path(self.temp.name).resolve() / "finalisation"
        self.here.mkdir()
        self.local = self.here / "local"
        self.local.mkdir()

    def test_default_revision_remains_v4(self):
        args = argument_parser().parse_args([])
        self.assertEqual(args.revision, "v4")
        self.assertIsNone(args.output)
        self.assertEqual(resolve_output(self.here, args.revision, args.output), self.local / "v4")

    def test_explicit_v5_and_output_parse(self):
        args = argument_parser().parse_args(["--revision", "v5", "--output", str(self.local / "rerun")])
        self.assertEqual(args.revision, "v5")
        self.assertEqual(args.output, self.local / "rerun")

    def test_fresh_private_destination_is_not_created_by_validation(self):
        dest = self.local / "audit" / "fresh"
        self.assertEqual(resolve_output(self.here, "v5", dest), dest)
        self.assertFalse(dest.exists())

    def test_frozen_revision_is_not_overwritten(self):
        frozen = self.local / "v5"
        frozen.mkdir()
        marker = frozen / "sentinel.txt"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            resolve_output(self.here, "v5", None)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_existing_empty_output_is_rejected(self):
        dest = self.local / "existing"
        dest.mkdir()
        with self.assertRaises(FileExistsError):
            resolve_output(self.here, "v5", dest)

    def test_new_destination_inside_frozen_revision_is_rejected(self):
        for revision in ("v3", "v4", "v5"):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                resolve_output(self.here, "v5", self.local / revision / "new-rerun")

    def test_existing_file_is_rejected(self):
        dest = self.local / "file"
        dest.write_text("preserve", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            resolve_output(self.here, "v5", dest)

    def test_private_root_itself_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_output(self.here, "v5", self.local)

    def test_outside_and_traversal_destinations_are_rejected(self):
        for dest in (self.here / "public", self.local / ".." / "escape", self.here / "local-other" / "fresh"):
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                resolve_output(self.here, "v5", dest)

    def test_symlink_escape_is_rejected_when_supported(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        link = self.local / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlink creation unavailable: {error}")
        with self.assertRaises(ValueError):
            resolve_output(self.here, "v5", link / "fresh")

    def test_semantic_digest_ignores_dictionary_key_order(self):
        first = {"a": 1, "nested": {"x": 2, "y": 3}}
        second = {"nested": {"y": 3, "x": 2}, "a": 1}
        self.assertEqual(semantic_json_digest(first), semantic_json_digest(second))

    def test_semantic_digest_preserves_values_and_list_order(self):
        self.assertNotEqual(semantic_json_digest({"a": 1}), semantic_json_digest({"a": 2}))
        self.assertNotEqual(semantic_json_digest([1, 2]), semantic_json_digest([2, 1]))

    def test_semantic_digest_rejects_non_finite_numbers(self):
        with self.assertRaises(ValueError):
            semantic_json_digest({"invalid": float("nan")})

    def test_code_closure_has_exact_nine_files_not_c4_runner(self):
        paths = code_dependencies(self.here)
        self.assertEqual(len(paths), 9)
        self.assertEqual(len(set(paths)), 9)
        self.assertIn("C3_construct_network.py", {p.name for p in paths})
        self.assertIn("C5_run_sensitivity_tests.py", {p.name for p in paths})
        self.assertNotIn("C4_calculate_scores.py", {p.name for p in paths})


if __name__ == "__main__":
    unittest.main()
