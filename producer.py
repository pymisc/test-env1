#!/usr/bin/env python3

"""
producer.py

Simulates a software build/release producer.

The script:
1. Creates a 256 MiB random binary artifact.
2. Calculates the artifact's SHA-256 checksum.
3. Creates a YAML metadata file containing:
   - artifact filename
   - file size
   - SHA-256 checksum
   - creation timestamp

This represents the producer side (Environment A)
of our cross-environment release simulation.
"""

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("/home/output")
PACKAGE_NAME = "packagefile.bin"
METADATA_NAME = "packagefile.yaml"

BLOCK_SIZE = "1M"
BLOCK_COUNT = 256


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def create_binary_file(output_file: Path) -> None:
    """Create a 256 MiB random binary file using dd."""

    print(f"Creating binary artifact: {output_file}")

    subprocess.run(
        [
            "dd",
            "if=/dev/urandom",
            f"of={output_file}",
            f"bs={BLOCK_SIZE}",
            f"count={BLOCK_COUNT}",
            "status=progress",
        ],
        check=True,
    )

    print("Artifact creation completed.")


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA-256 checksum without loading the entire file into memory."""

    print("Calculating SHA-256 checksum...")

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    checksum = sha256.hexdigest()

    print(f"SHA-256: {checksum}")

    return checksum


def create_metadata(
    metadata_file: Path,
    package_file: Path,
    checksum: str,
) -> None:
    """Create YAML metadata describing the generated artifact."""

    creation_time = datetime.now(timezone.utc).isoformat()

    metadata = f"""artifact:
  filename: {package_file.name}
  size_bytes: {package_file.stat().st_size}
  sha256: {checksum}
  created_at: "{creation_time}"
"""

    metadata_file.write_text(metadata, encoding="utf-8")

    print(f"Metadata created: {metadata_file}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate artifact and metadata."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    package_file = OUTPUT_DIR / PACKAGE_NAME
    metadata_file = OUTPUT_DIR / METADATA_NAME

    create_binary_file(package_file)

    checksum = calculate_sha256(package_file)

    create_metadata(
        metadata_file=metadata_file,
        package_file=package_file,
        checksum=checksum,
    )

    print()
    print("Producer completed successfully.")
    print(f"Artifact : {package_file}")
    print(f"Metadata : {metadata_file}")


if __name__ == "__main__":
    main()