import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import data, run


def fixture(count=123):
    labels = {f"h{i}": {"hypothesis": f"Hypothesis {i}."} for i in range(17)}
    return {"labels": labels, "documents": [{"id": i, "text": f"Contract {i}.\n  Kept verbatim.",
        "annotation_sets": [{"annotations": {key: {"choice": "NotMentioned"} for key in labels}}]}
        for i in range(count - 1, -1, -1)]}


class DataTests(unittest.TestCase):
    def test_official_schema_retains_full_text_and_hypothesis_order(self):
        source = fixture()
        rows = data.normalize(source, "test")
        self.assertEqual([row["id"] for row in rows], list(range(123)))
        self.assertEqual(rows[0]["contract"], "Contract 0.\n  Kept verbatim.")
        self.assertEqual(list(rows[0]["hypotheses"]), list(source["labels"]))
        self.assertEqual(set(rows[0]["labels"].values()), {"not_mentioned"})

    def test_schema_rejects_duplicate_document_ids_and_missing_annotations(self):
        source = fixture()
        source["documents"][0]["id"] = source["documents"][1]["id"]
        with self.assertRaises(ValueError):
            data.normalize(source, "test")
        source = fixture()
        del source["documents"][0]["annotation_sets"][0]["annotations"]["h0"]
        with self.assertRaises(ValueError):
            data.normalize(source, "test")

    def test_anchor_selection_is_independent_of_labels_and_text(self):
        rows = data.normalize(fixture(), "test")
        kwargs = dict(seed=20260922, documents=30, anchors_per_document=1)
        first = data.select_anchors(rows, **kwargs)
        changed = copy.deepcopy(rows)
        for row in changed:
            row["contract"] = "Different contract."
            row["hypotheses"] = {key: "Different text." for key in row["hypotheses"]}
            row["labels"] = {key: "contradiction" for key in row["labels"]}
        second = data.select_anchors(changed[::-1], **kwargs)
        selected = lambda panel: [(row["id"], row["anchors"]) for row in panel]
        self.assertEqual(selected(first), selected(second))
        self.assertEqual(len({row["id"] for row in first}), 30)

    def test_development_exclusion_panel_is_disjoint(self):
        rows = data.normalize(fixture(61), "dev")
        excluded = set(range(30))
        panel = data.select_anchors(rows, seed=20260921, documents=10,
                                   anchors_per_document=3, excluded_ids=excluded)
        self.assertFalse(excluded & {row["id"] for row in panel})
        self.assertTrue(all(len(set(row["anchors"])) == 3 for row in panel))

    def test_unverified_archive_is_rejected_before_parsing(self):
        with patch.object(data.zipfile, "ZipFile") as archive:
            with self.assertRaises(ValueError):
                data.read_split(b"not the official release", "test")
        archive.assert_not_called()

    def test_modified_panel_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "test123").mkdir()
            (root / "test123" / "input_data.jsonl").write_text("{}\n")
            with self.assertRaises(ValueError):
                data.load_panel(root, "test123")

    def test_baseline_and_anchor_request_counts(self):
        rows = data.normalize(fixture(), "test")
        panel = data.select_anchors(rows, seed=20260922, documents=30, anchors_per_document=1)
        self.assertEqual(len(list(run.jobs(rows, "test123", "example"))), 123)
        self.assertEqual(len(list(run.jobs(panel, "test_anchor30", "example"))), 360)

    def test_dry_run_does_not_read_credentials_or_call_network(self):
        rows = data.normalize(fixture(), "test")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan"
            with patch.object(run, "load_panel", return_value=rows), \
                    patch.object(run.providers, "connection_from_environment") as connection, \
                    patch.object(run.providers, "predict") as predict:
                result = run.main(["--panel", "test123", "--adapter", "jev", "--model", "jev-1.13.0",
                                   "--model-key", "jev", "--output-dir", str(output)])
            self.assertEqual(result, 0)
            connection.assert_not_called()
            predict.assert_not_called()
            manifest = json.loads((output / "run.json").read_text())
            self.assertEqual(manifest["collection_kind"], "offline_plan")
            self.assertFalse((output / "predictions.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
