#!/usr/bin/env python3
"""Record the exact local CSV datasets used by the frozen DTI benchmark.

The three CSVs are expected to be byte-identical to the pinned ``full.csv``
files in the official DrugBAN repository.  The manifest therefore records both
the usual SHA256 checksum and the Git-blob SHA1 used to verify that provenance.
It does not imply that the original upstream data may be redistributed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


DATASETS = ("biosnap", "human", "bindingdb")

# On 2026-08-28, the local benchmark inputs were independently compared with
# these blob objects.  Pin the source commit so the manuscript does not depend
# on a moving ``main`` branch.  The repository's dataset README identifies the
# upstream origins, while the original providers' terms still govern reuse.
DRUGBAN_REPOSITORY = "https://github.com/peizhenbai/DrugBAN"
DRUGBAN_COMMIT = "9923f8c99959e00263103ff9ac61ba0eaccc8e02"
UPSTREAM_DATASETS = {
    "biosnap": {
        "repository_path": "datasets/biosnap/full.csv",
        "git_blob_sha1": "8075689605257768b88eacb361b8ee7c2e7c3be5",
        "documented_origin": "BioSNAP dataset distributed by MolTrans",
        "documented_origin_url": "https://github.com/kexinhuang12345/MolTrans",
        "citation_key": "huang2021moltrans",
    },
    "human": {
        "repository_path": "datasets/human/full.csv",
        "git_blob_sha1": "711273c6f6da565ade72ad9ef615521f6743f293",
        "documented_origin": "Human dataset distributed by TransformerCPI",
        "documented_origin_url": "https://github.com/lifanchen-simm/transformerCPI",
        "citation_key": "chen2020transformercpi",
    },
    "bindingdb": {
        "repository_path": "datasets/bindingdb/full.csv",
        "git_blob_sha1": "a9aad592e945505bf22c5bd606e700b189181ba1",
        "documented_origin": "BindingDB public database",
        "documented_origin_url": "https://www.bindingdb.org/bind/index.jsp",
        "citation_key": "liu2007bindingdb",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha1(path: Path) -> str:
    """Return the SHA1 Git would assign to ``path`` as a blob object."""

    digest = hashlib.sha1()
    digest.update(f"blob {path.stat().st_size}\0".encode("ascii"))
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="/mnt/sda/fulaiyi/DTI_datasets")
    parser.add_argument("--output", default="dataset_manifest.json")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    records = []
    for dataset in DATASETS:
        path = data_dir / f"{dataset}_full.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        frame = pd.read_csv(path)
        required = {"SMILES", "Protein", "Y"}
        if not required.issubset(frame.columns):
            raise RuntimeError(f"{path} lacks required columns: {sorted(required - set(frame.columns))}")
        upstream = UPSTREAM_DATASETS[dataset]
        blob_sha1 = git_blob_sha1(path)
        records.append(
            {
                "dataset": dataset,
                "file": str(path),
                "sha256": sha256(path),
                "git_blob_sha1": blob_sha1,
                "bytes": path.stat().st_size,
                "columns": list(frame.columns),
                "rows": int(len(frame)),
                "unique_smiles": int(frame["SMILES"].nunique()),
                "unique_proteins": int(frame["Protein"].nunique()),
                "positive_rows": int((frame["Y"] == 1).sum()),
                "negative_rows": int((frame["Y"] == 0).sum()),
                "provenance": {
                    "exact_upstream_snapshot_match": blob_sha1 == upstream["git_blob_sha1"],
                    "upstream_repository": DRUGBAN_REPOSITORY,
                    "upstream_commit": DRUGBAN_COMMIT,
                    "upstream_commit_url": f"{DRUGBAN_REPOSITORY}/tree/{DRUGBAN_COMMIT}",
                    **upstream,
                    "licence_note": (
                        "The DrugBAN repository is MIT-licensed, but the original "
                        "dataset providers' terms govern data reuse and redistribution."
                    ),
                },
            }
        )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "provenance_note": (
                    "Exact content match is checked against a pinned Git blob; this does not "
                    "replace the original providers' licence and terms-of-use review."
                ),
                "datasets": records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
