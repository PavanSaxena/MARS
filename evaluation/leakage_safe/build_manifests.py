"""Generate leakage-safe split manifests and dataset audit artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.leakage_safe.dataset import REPO_ROOT, build_split_manifest, load_cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MARS evaluation.leakage_safe manifests.")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation" / "leakage_safe" / "artifacts" / "split_manifest.json"),
        help="Path for the generated split manifest JSON.",
    )
    args = parser.parse_args()

    cases = load_cases()
    manifest = build_split_manifest(cases, Path(args.output))
    print(json.dumps({
        "output": args.output,
        "total_cases": manifest["audit"]["total_cases"],
        "splits": {name: data["n"] for name, data in manifest["splits"].items()},
        "chronology_violations": len(manifest["audit"]["chronology_violations"]),
        "duplicate_case_ids": len(manifest["audit"]["duplicate_case_ids"]),
        "duplicate_content_groups": len(manifest["audit"]["duplicate_content_groups"]),
    }, indent=2))


if __name__ == "__main__":
    main()

