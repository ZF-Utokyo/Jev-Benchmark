"""Rebuild the frozen panels from the hash-pinned official ContractNLI archive."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import random
import sys
from urllib.request import urlopen
import zipfile

from .protocol import LABELS, load_json

SOURCE_URL = "https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip"
SOURCE_PAGE = "https://stanfordnlp.github.io/contract-nli/"
CITATION_URL = "https://aclanthology.org/2021.findings-emnlp.164/"
ARCHIVE_SHA256 = "e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b"
MEMBER_SHA256 = {
    "dev": "310af7d661d2ab50ee3700169cef524c75f39fb296bbf5a515c229eb0f42e68e",
    "test": "460267b56052a2dc5aead98eb35eadef9e6734d5723d37b4a9790e410f812387",
}
PANEL_SHA256 = {
    "dev30": "7210c08b5736b5a38193802dd73dc3faf1f38031a942f112f4b31a665e058518",
    "dev_anchor10": "96bf335cac9ef864fb3a20799109bff7f12fcf2da8285e84bbb8f97ac2107896",
    "test123": "a2e7dbff61687dea33ee4361874e259cc666de5048fad137ef63aa521af28021",
    "test_anchor30": "3ead4848c6e8d931bfe95f684ada82f58b65e0bd8a41c9d63199bd5f0c0ae0e0",
}
PANEL_SEEDS = {"dev30": 20260920, "dev_anchor10": 20260921,
               "test123": 20260922, "test_anchor30": 20260922}
LABEL_MAP = {"Entailment": "entailment", "Contradiction": "contradiction", "NotMentioned": "not_mentioned"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def serialize_rows(rows):
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                   for row in rows).encode("utf-8")


def normalize(dataset, split):
    """Preserve full texts and official hypothesis insertion order."""
    definitions, documents = dataset.get("labels"), dataset.get("documents")
    if (not isinstance(definitions, dict) or len(definitions) != 17 or
            not isinstance(documents, list) or len(documents) != {"dev": 61, "test": 123}[split]):
        raise ValueError("invalid_official_schema")
    hypotheses = {}
    for key, definition in definitions.items():
        if (not isinstance(key, str) or not key or not isinstance(definition, dict)
                or not isinstance(definition.get("hypothesis"), str) or not definition["hypothesis"].strip()):
            raise ValueError("invalid_hypothesis")
        hypotheses[key] = definition["hypothesis"]
    rows, seen = [], set()
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("invalid_document")
        document_id, contract = document.get("id"), document.get("text")
        annotations = document.get("annotation_sets")
        if (type(document_id) is not int or document_id in seen or
                not isinstance(contract, str) or not contract.strip() or
                not isinstance(annotations, list) or len(annotations) != 1 or
                not isinstance(annotations[0], dict)):
            raise ValueError("invalid_document")
        seen.add(document_id)
        annotations = annotations[0].get("annotations")
        if not isinstance(annotations, dict) or set(annotations) != set(hypotheses):
            raise ValueError("invalid_annotation_ids")
        labels = {}
        for key in hypotheses:
            value = annotations[key]
            if not isinstance(value, dict) or value.get("choice") not in LABEL_MAP:
                raise ValueError("invalid_annotation_label")
            labels[key] = LABEL_MAP[value["choice"]]
        rows.append({"id": document_id, "contract": contract, "hypotheses": dict(hypotheses), "labels": labels})
    return sorted(rows, key=lambda row: row["id"])


def select_anchors(rows, *, seed, documents, anchors_per_document, excluded_ids=()):
    eligible = [row for row in sorted(rows, key=lambda row: row["id"]) if row["id"] not in excluded_ids]
    selected = random.Random(seed).sample(eligible, documents)
    panel = []
    for row in selected:
        digest = hashlib.sha256(f'{seed}:anchors:{row["id"]}'.encode()).digest()
        anchors = random.Random(int.from_bytes(digest[:8], "big")).sample(
            list(row["hypotheses"]), anchors_per_document)
        panel.append({**row, "anchors": anchors})
    return panel


def read_split(archive_bytes, split):
    if sha256(archive_bytes) != ARCHIVE_SHA256:
        raise ValueError("official_archive_checksum_mismatch")
    member = f"contract-nli/{split}.json"
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = [info for info in archive.infolist() if info.filename == member]
        if len(members) != 1 or members[0].file_size > 32 * 1024 * 1024:
            raise ValueError("invalid_archive_member")
        content = archive.read(member)
    if sha256(content) != MEMBER_SHA256[split]:
        raise ValueError("official_member_checksum_mismatch")
    return normalize(load_json(content), split)


def build_panels(archive_bytes, include_development=False):
    test = read_split(archive_bytes, "test")
    panels = {"test123": test, "test_anchor30": select_anchors(
        test, seed=20260922, documents=30, anchors_per_document=1)}
    if include_development:
        dev = read_split(archive_bytes, "dev")
        dev30 = random.Random(20260920).sample(dev, 30)
        panels["dev30"] = dev30
        panels["dev_anchor10"] = select_anchors(dev, seed=20260921, documents=10,
            anchors_per_document=3, excluded_ids={row["id"] for row in dev30})
        if {row["id"] for row in dev} & {row["id"] for row in test}:
            raise ValueError("split_overlap")
    return panels


def write_panels(panels, destination):
    """Require historical byte hashes; refuse to alter an existing dataset."""
    serialized = {name: serialize_rows(rows) for name, rows in panels.items()}
    if any(sha256(content) != PANEL_SHA256[name] for name, content in serialized.items()):
        raise ValueError("prepared_panel_checksum_mismatch")
    for name in panels:
        if (destination / name).exists():
            raise FileExistsError("panel_already_exists")
    for name, rows in panels.items():
        split = "dev" if name.startswith("dev") else "test"
        manifest = {
            "dataset": "ContractNLI", "panel": name, "split": split,
            "source_url": SOURCE_URL, "source_sha256": ARCHIVE_SHA256,
            "source_member": f"contract-nli/{split}.json", "source_member_sha256": MEMBER_SHA256[split],
            "sample_file": "input_data.jsonl", "sample_sha256": PANEL_SHA256[name],
            "seed": PANEL_SEEDS[name], "sample_ids": [row["id"] for row in rows],
            "hypothesis_ids": list(rows[0]["hypotheses"]),
            "anchors_by_document": {str(row["id"]): row["anchors"] for row in rows if "anchors" in row},
            "citation_url": CITATION_URL, "license": "CC-BY-4.0",
            "attribution": "ContractNLI by Yuta Koreeda and Christopher Manning (2021)",
        }
        folder = destination / name
        folder.mkdir(parents=True)
        (folder / "input_data.jsonl").write_bytes(serialized[name])
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def load_panel(data_dir, name):
    if name not in PANEL_SHA256:
        raise ValueError("unknown_panel")
    content = (data_dir / name / "input_data.jsonl").read_bytes()
    if sha256(content) != PANEL_SHA256[name]:
        raise ValueError("prepared_panel_checksum_mismatch")
    return [load_json(line) for line in content.splitlines() if line.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, help="Existing official archive; otherwise download it")
    parser.add_argument("--include-development", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.archive:
            archive = args.archive.read_bytes()
        else:
            with urlopen(SOURCE_URL, timeout=120) as response:
                archive = response.read(128 * 1024 * 1024 + 1)
            if len(archive) > 128 * 1024 * 1024:
                raise ValueError("archive_size_limit")
        panels = build_panels(archive, args.include_development)
        write_panels(panels, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        print("Data preparation failed; verify the archive, destination and checksums.", file=sys.stderr)
        return 1
    print(f"Prepared {len(panels)} verified panels; no inference performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
