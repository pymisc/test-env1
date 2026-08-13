#!/usr/bin/env python3

"""
producer.py

Simulates the producer side of a split-environment software
build / qualification workflow.

The script performs the following steps:

1. Creates a 256 MiB random binary artifact.
2. Calculates the artifact's SHA-256 checksum.
3. Creates a YAML metadata/manifest file containing:
   - artifact filename
   - artifact size
   - SHA-256 checksum
   - creation timestamp
4. Uploads the binary artifact to a shared S3 bucket.
5. Uploads the YAML manifest to S3 after the binary upload completes.

The YAML manifest is uploaded last intentionally. In a split-environment
design, the consumer can treat the presence of the manifest as an
indication that the corresponding binary artifact is ready for processing.
"""

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Local directory where generated files will be stored.
OUTPUT_DIR = Path("/home/output")

# Artifact and manifest filenames.
PACKAGE_NAME = "packagefile.bin"
METADATA_NAME = "packagefile.yaml"

# dd configuration:
# 1 MiB x 256 blocks = 256 MiB artifact.
BLOCK_SIZE = "1M"
BLOCK_COUNT = 256

# Shared S3 location used to transfer artifacts between environments.
S3_BUCKET = "s3://split-env-data"

# AWS CLI profile already configured on the producer machine.
AWS_PROFILE = "s3profile"


# ---------------------------------------------------------------------------
# Artifact creation
# ---------------------------------------------------------------------------

def create_binary_file(output_file: Path) -> None:
    """
    Create a 256 MiB random binary artifact using the Linux dd command.

    /dev/urandom is used so the generated file contains random data,
    making it suitable for simulating a real build/release artifact.
    """

    print()
    print(f"[1/5] Creating binary artifact: {output_file}")

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


# ---------------------------------------------------------------------------
# Checksum generation
# ---------------------------------------------------------------------------

def calculate_sha256(file_path: Path) -> str:
    """
    Calculate the SHA-256 checksum of a file.

    The file is read in 1 MiB chunks rather than loading the entire
    artifact into memory. This allows the same approach to work with
    much larger artifacts.
    """

    print()
    print(f"[2/5] Calculating SHA-256 checksum: {file_path.name}")

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    checksum = sha256.hexdigest()

    print(f"SHA-256: {checksum}")

    return checksum


# ---------------------------------------------------------------------------
# Manifest creation
# ---------------------------------------------------------------------------

def create_metadata(
    metadata_file: Path,
    package_file: Path,
    checksum: str,
) -> None:
    """
    Create a YAML manifest describing the generated artifact.

    The consumer environment will later use this metadata to identify
    the artifact and verify that its SHA-256 checksum matches.
    """

    print()
    print(f"[3/5] Creating metadata manifest: {metadata_file}")

    creation_time = datetime.now(timezone.utc).isoformat()

    metadata = f"""artifact:
  filename: {package_file.name}
  size_bytes: {package_file.stat().st_size}
  sha256: {checksum}
  created_at: "{creation_time}"
"""

    metadata_file.write_text(metadata, encoding="utf-8")

    print("Metadata creation completed.")


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------

def upload_to_s3(file_path: Path) -> None:
    """
    Upload a file to the shared S3 bucket using the AWS CLI.

    subprocess.run(..., check=True) causes the script to stop immediately
    if the AWS CLI command returns a non-zero exit code.
    """

    destination = f"{S3_BUCKET}/{file_path.name}"

    print(f"Uploading {file_path.name} -> {destination}")

    subprocess.run(
        [
            "aws",
            "s3",
            "--profile",
            AWS_PROFILE,
            "cp",
            str(file_path),
            destination,
        ],
        check=True,
    )

    print(f"Upload completed: {file_path.name}")


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Generate the artifact and manifest, then publish both to S3.
    """

    # Create the local output directory if it does not already exist.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    package_file = OUTPUT_DIR / PACKAGE_NAME
    metadata_file = OUTPUT_DIR / METADATA_NAME

    # Step 1: Generate the simulated software artifact.
    create_binary_file(package_file)

    # Step 2: Calculate the artifact checksum.
    checksum = calculate_sha256(package_file)

    # Step 3: Generate the YAML manifest.
    create_metadata(
        metadata_file=metadata_file,
        package_file=package_file,
        checksum=checksum,
    )

    # Step 4:
    # Upload the binary artifact FIRST.
    #
    # This is intentional. The consumer should never see the manifest
    # before the corresponding binary artifact has finished uploading.
    print()
    print("[4/5] Uploading binary artifact to S3...")
    upload_to_s3(package_file)

    # Step 5:
    # Upload the manifest LAST.
    #
    # Later, the consumer can watch for new manifest files and treat
    # their appearance as the "artifact ready" signal.
    print()
    print("[5/5] Uploading metadata manifest to S3...")
    upload_to_s3(metadata_file)

    # Final summary.
    print()
    print("=" * 60)
    print("Producer completed successfully.")
    print("=" * 60)
    print(f"Local artifact : {package_file}")
    print(f"Local manifest : {metadata_file}")
    print(f"S3 artifact    : {S3_BUCKET}/{PACKAGE_NAME}")
    print(f"S3 manifest    : {S3_BUCKET}/{METADATA_NAME}")
    print(f"SHA-256        : {checksum}")


if __name__ == "__main__":
    main()