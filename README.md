# test-env1 — Producer Environment

`test-env1` simulates the **producer side** of a split-environment build and qualification workflow.

The repository generates a binary artifact, creates a SHA-256 manifest, assigns a unique UUID to each submission, and publishes the artifact to a shared Amazon S3 bucket.

## Architecture

```text
┌─────────────────────────────┐
│        GitHub Actions       │
│    Producer CI Pipeline     │
│                             │
│  push to main / manual run  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│        producer.py          │
│                             │
│  1. Generate UUID           │
│  2. Create 256 MiB .bin     │
│  3. Calculate SHA-256       │
│  4. Create YAML manifest    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│          AWS S3             │
│      split-env-data         │
│                             │
│ incoming/<UUID>/            │
│ ├── packagefile.bin         │
│ └── packagefile.yaml        │
└─────────────────────────────┘
```

## Workflow

The producer performs the following operations:

1. Generates a unique **UUID** for the submission.
2. Creates a **256 MiB random binary artifact**.
3. Calculates its **SHA-256 checksum**.
4. Creates a YAML metadata manifest.
5. Uploads `packagefile.bin` to S3.
6. Uploads `packagefile.yaml` **last**.

The manifest is intentionally uploaded last and acts as the **submission-ready signal** for the consumer environment.

S3 layout:

```text
s3://split-env-data/

incoming/
└── <UUID>/
    ├── packagefile.bin
    └── packagefile.yaml
```

## Artifact Manifest

Example `packagefile.yaml`:

```yaml
job:
  id: 6f57c42b-953c-4db5-8564-c037c4ddc973

artifact:
  filename: packagefile.bin
  size_bytes: 268435456
  sha256: <SHA-256 checksum>
  created_at: "2026-08-14T17:00:00+00:00"
```

The UUID acts as the correlation ID for the artifact throughout the qualification workflow.

## CI Pipeline

The GitHub Actions workflow is defined in:

```text
.github/workflows/ci.yaml
```

The **Producer CI Pipeline** runs on:

- Pushes to `main`
- Manual `workflow_dispatch`

The pipeline:

```text
Checkout
   │
   ▼
Setup Python
   │
   ▼
Authenticate to AWS
   │
   │ OIDC + STS
   ▼
Assume IAM Role
test-env1-producer
   │
   ▼
Run producer.py
   │
   ▼
Upload artifacts to S3
```

## AWS Authentication

GitHub Actions authenticates to AWS using:

```text
GitHub OIDC
     │
     ▼
AWS STS
AssumeRoleWithWebIdentity
     │
     ▼
test-env1-producer
     │
     ▼
Amazon S3
```

No permanent AWS access keys are stored in the repository.

## Local Run

When running locally with an AWS CLI profile:

```bash
AWS_PROFILE=s3profile python3 producer.py
```

In GitHub Actions, AWS credentials are supplied automatically through **OIDC + AWS STS**.

## Consumer Handoff

The corresponding consumer/scheduler environment is implemented separately in `test-env2`.

`test-env2` periodically scans the shared S3 bucket for:

```text
incoming/<UUID>/packagefile.yaml
```

The presence of this manifest indicates that the producer has completed publishing the corresponding artifact and the submission is ready for qualification.