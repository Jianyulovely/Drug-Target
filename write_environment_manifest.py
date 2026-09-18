#!/usr/bin/env python3
"""Write a machine-readable runtime manifest for the audited DTI release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path


PACKAGE_NAMES = ("numpy", "pandas", "scipy", "scikit-learn", "matplotlib", "torch", "rdkit")
SCRIPT_NAMES = (
    "paper_benchmark.py",
    "prepare_drugban_splits.py",
    "run_drugban_fold.py",
    "run_drugban_queue.sh",
    "plot_paper_results.py",
    "generate_manuscript_results.py",
    "verify_paper_coverage.py",
    "verify_split_integrity.py",
    "final_paper_audit.py",
    "write_dataset_manifest.py",
    "write_environment_manifest.py",
    "postprocess_after_drugban.sh",
)
CORE_SCRIPT_ENV = "DTI_CORE_PATH"


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nvidia_smi() -> list[str] | None:
    command = [
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader",
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def torch_details() -> dict[str, object]:
    try:
        import torch
    except ImportError:
        return {"available": False}
    return {
        "available": True,
        "version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": int(torch.cuda.device_count()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/mnt/sda/fulaiyi/dti_paper_20260826_v2")
    parser.add_argument("--output", help="Default: <root>/source_data/environment_manifest.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output).resolve() if args.output else root / "source_data" / "environment_manifest.json"
    core_path = Path(os.environ[CORE_SCRIPT_ENV]).resolve() if os.environ.get(CORE_SCRIPT_ENV) else None
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "packages": {name: package_version(name) for name in PACKAGE_NAMES},
        "torch": torch_details(),
        "nvidia_smi": nvidia_smi(),
        "key_script_sha256": {name: sha256(root / name) for name in SCRIPT_NAMES},
        "external_core": {
            "environment_variable": CORE_SCRIPT_ENV,
            "path": str(core_path) if core_path else None,
            "sha256": sha256(core_path) if core_path else None,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
