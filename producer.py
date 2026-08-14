#!/usr/bin/env python3

"""
producer.py

Simulates the producer side of a split-environment software
build / qualification workflow.

Workflow:

1. Generate a unique job ID (UUID) for the submission.
2. Create a 256 MiB random binary artifact.
3. Calculate the artifact's SHA-256 checksum.
4. Create a YAML metadata manifest containing:
   - job ID
   - artifact filename
   - artifact size
   - SHA-256 checksum
   - creation timestamp
5. Upload the binary artifact to:

       s3://split-env-data/incoming/<job-id>/packagefile.bin

6. Upload the YAML manifest LAST to:

       s3://split-env-data/incoming/<job-id>/packagefile.yaml

The manifest is intentionally uploaded last. The consumer environment
can treat the presence of packagefile.yaml as an indication that the
corresponding binary artifact has been completely published and is
ready for processing.
"""

import hashlib
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Local directory where generated files are stored.
OUTPUT_DIR = Path("output")

# Artifact and manifest filenames.
PACKAGE_NAME = "packagefile.bin"
METADATA_NAME = "packagefile.yaml"

# Binary artifact size:
# 1 MiB x 256 blocks = 256 MiB.
BLOCK_SIZE = "1M"
BLOCK_COUNT = 256

# Shared S3 bucket used to exchange data between environments.
S3_BUCKET = "s3://split-env-data"

# S3 prefix where new submissions are published.
S3_INCOMING_PREFIX = "incoming"


# ---------------------------------------------------------------------------
# Artifact creation
# ---------------------------------------------------------------------------

def create_binary_file(output_file: Path) -> None:
    """
    Create a 256 MiB random binary artifact using the Linux dd command.

    /dev/urandom is used to generate random binary data and simulate
    a software or firmware build artifact.
    """

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


# ---------------------------------------------------------------------------
# Checksum calculation
# ---------------------------------------------------------------------------

def calculate_sha256(file_path: Path) -> str:
    """
    Calculate and return the SHA-256 checksum of a file.

    The file is read in 1 MiB chunks instead of loading the entire
    artifact into memory. This allows the same function to work
    efficiently with much larger artifacts.
    """

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
    job_id: str,
) -> None:
    """
    Create a YAML manifest describing the generated artifact.

    The manifest contains the unique job ID as well as information
    required by the consumer to locate and validate the artifact.
    """

    creation_time = datetime.now(timezone.utc).isoformat()

    metadata = f"""job:
  id: {job_id}

artifact:
  filename: {package_file.name}
  size_bytes: {package_file.stat().st_size}
  sha256: {checksum}
  created_at: "{creation_time}"
"""

    metadata_file.write_text(metadata, encoding="utf-8")

    print(f"Metadata file created: {metadata_file}")


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------

def upload_to_s3(
    file_path: Path,
    job_id: str,
) -> None:
    """
    Upload a file to the incoming/<job-id>/ location in the shared
    S3 bucket.

    AWS credentials are intentionally NOT configured inside this
    application.

    Examples:

    Local development:
        AWS_PROFILE=s3profile python3 producer.py

    GitHub Actions:
        Credentials are provided through the GitHub OIDC / AWS STS
        workflow before this script executes.

    check=True causes subprocess.run() to raise an exception if the
    AWS CLI command returns a non-zero exit code.
    """

    destination = (
        f"{S3_BUCKET}/"
        f"{S3_INCOMING_PREFIX}/"
        f"{job_id}/"
        f"{file_path.name}"
    )

    print(f"Uploading {file_path} -> {destination}")

    subprocess.run(
        [
            "aws",
            "s3",
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
    Execute the producer workflow.

    The main function owns the workflow sequencing while the individual
    functions remain focused on performing one specific operation.
    """

    # Ensure the local output directory exists.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate a globally unique identifier for this submission.
    #
    # UUIDs allow multiple producers or CI jobs to submit work
    # concurrently without requiring a centralized counter.
    job_id = str(uuid.uuid4())

    package_file = OUTPUT_DIR / PACKAGE_NAME
    metadata_file = OUTPUT_DIR / METADATA_NAME

    # -----------------------------------------------------------------------
    # Submission information
    # -----------------------------------------------------------------------

    print()
    print("=" * 60)
    print("Producer submission")
    print("=" * 60)
    print(f"Job ID: {job_id}")

    # -----------------------------------------------------------------------
    # Step 1: Generate the simulated software artifact.
    # -----------------------------------------------------------------------

    print()
    print("[1/5] Generating binary artifact...")

    create_binary_file(package_file)

    # -----------------------------------------------------------------------
    # Step 2: Calculate the SHA-256 checksum.
    # -----------------------------------------------------------------------

    print()
    print("[2/5] Calculating artifact SHA-256 checksum...")

    checksum = calculate_sha256(package_file)

    # -----------------------------------------------------------------------
    # Step 3: Create the YAML artifact manifest.
    # -----------------------------------------------------------------------

    print()
    print("[3/5] Creating artifact metadata manifest...")

    create_metadata(
        metadata_file=metadata_file,
        package_file=package_file,
        checksum=checksum,
        job_id=job_id,
    )

    # -----------------------------------------------------------------------
    # Step 4: Upload the binary artifact FIRST.
    #
    # The artifact must be completely available before the manifest is
    # published. This prevents the consumer from discovering a manifest
    # that references an artifact that is still being uploaded.
    # -----------------------------------------------------------------------

    print()
    print("[4/5] Uploading binary artifact to S3...")

    upload_to_s3(
        file_path=package_file,
        job_id=job_id,
    )

    # -----------------------------------------------------------------------
    # Step 5: Upload the manifest LAST.
    #
    # The consumer can treat the presence of packagefile.yaml as the
    # "submission ready" signal.
    # -----------------------------------------------------------------------

    print()
    print("[5/5] Uploading metadata manifest to S3...")

    upload_to_s3(
        file_path=metadata_file,
        job_id=job_id,
    )

    # -----------------------------------------------------------------------
    # Final summary
    # -----------------------------------------------------------------------

    s3_job_path = (
        f"{S3_BUCKET}/"
        f"{S3_INCOMING_PREFIX}/"
        f"{job_id}"
    )

    print()
    print("=" * 60)
    print("Producer completed successfully.")
    print("=" * 60)
    print(f"Job ID         : {job_id}")
    print(f"Local artifact : {package_file}")
    print(f"Local manifest : {metadata_file}")
    print(f"S3 location    : {s3_job_path}/")
    print(f"S3 artifact    : {s3_job_path}/{PACKAGE_NAME}")
    print(f"S3 manifest    : {s3_job_path}/{METADATA_NAME}")
    print(f"SHA-256        : {checksum}")


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()