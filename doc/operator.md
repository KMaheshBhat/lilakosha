# LilaKosha Pipeline Operational Guide

This document defines the interface commands, environmental profiles, step-by-step workflows, and state intervention modules required to initialize, monitor, and execute the LilaKosha data refinement and training engine.

## Prerequisites & Environment Matrix

### Hardware Verification

* **Minimum Requirement:** NVIDIA GPU with a minimum of **12 GB VRAM** (e.g., RTX 4070, RTX 3060 12GB).
* **Workspace Sandbox:** Developed and validated inside **WSL2 (Ubuntu)** environments.

### Base Software Layers

* Python 3.10+
* [uv](https://docs.astral.sh/uv/) (Ultra-fast Python packaging manager)
* High-performance text processing/inference servers running locally (e.g., `llama-server` or `litert-lm serve`) to power the localized annotation pipelines.

## Setup & Initialization

### 1. Workspace Installation

Initialize and synchronize your isolated virtual environment through `uv`:

```bash
uv init
uv sync
```

### 2. Environmental Volumes Staging

Establish your local persistent paths before executing active pipeline components. Copy `example.env` into a functional environment profile:

```bash
cp example.env .env
source .env
```

Your `.env` profile exports the following fundamental data vectors to the workspace orchestration wrapper:

```bash
export LILAKOSHA_VOLUME_RAW=/tmp/lk-dry/raw
export LILAKOSHA_VOLUME_PROCESSED=/tmp/lk-dry/processed
export LILAKOSHA_VOLUME_MODELS=/tmp/lk-dry/models
export LILAKOSHA_VOLUME_EXPORTS=/tmp/lk-dry/exports
```

## Execution Interface Control

The LilaKosha execution architecture wraps around standard orchestration manifests via a unified runner script. Trailing CLI configurations can pass overrides dynamically using the `--key value` format.

```bash
./run.sh pipeline/<pipeline-config>.yml [options]
```

### Step-by-Step Operator Manual

#### 1. Bootstrap Workspace Infrastructure

```bash
./run.sh pipeline/10-init.yml
```

Maps out local storage volumes, builds out structural internal folder depths, and stages target channel directory states.

#### 2. Ingest and Normalize Corpus Tracks

```bash
./run.sh pipeline/20-ingest.yml
```

Pipes, splits, and maps incoming unstructured text files into standardized, standalone `{UUIDv7}.json` tracking assets compliant with the shared Common Data Model (CDM) ledger.

#### 3. Run Refinement and Synthetics (Idempotent Sweep)

```bash
./run.sh pipeline/30-refine.yml
```

Executes character profile extraction, safety dial scoring, genre grouping, and formatting normalizations.

* **Guardrails:** This step utilizes explicit **idempotency checks** and checks the top-level metadata for health flags. It immediately passes over completed assets or rows marked defective by telemetry.

#### 4. Execute Data Telemetry & Validation Reports

```bash
./run.sh pipeline/35-report-records.yml [options]
```

Evaluates structural validation criteria and profiles dataset distribution matrices.

##### Advanced Operational Flags:

* **In-Flight Dashboard (Safe Watch Mode):** Process data validation entirely in-memory without mutating files on disk. Perfect for real-time monitoring loops while the refinement engines are actively executing:

```bash
watch -n 60 "./run.sh pipeline/35-report-records.yml --hide_anomaly_details true --audit_only true"
```

* **Authoritative Ingestion Gatekeeping:** Stamp definitive `healthy: true` or `healthy: false` indicators across all records to isolate corrupt fields before a training job:

```bash
./run.sh pipeline/35-report-records.yml --hide_anomaly_details true
```

* **Clear State and Force Retries:** Wipe all health tags entirely back to schema defaults (`None`) to make files look completely fresh for upstream pipeline modules but will retain the refinements:

```bash
./run.sh pipeline/35-report-records.yml --reset_health true
```

#### 5. Surgical Data Interventions (The Scalpel Engine)

If anomalous or corrupted records are isolated, the pipeline provides `25-scalpel-*` sweeps to reset targeted blocks of fields back to their unrefined CDM baselines. These scripts accept dynamic bound tags (`--start_uuid` and `--stop_uuid`) to isolate specific rows.

* **Target and Rollback an Isolated Record:**

```bash
./run.sh pipeline/25-scalpel-characters.yml --start_uuid 019ed224-2866-7db3-9648-196a3451d42a --stop_uuid 019ed224-2866-7db3-9648-196a3451d42a
./run.sh pipeline/25-scalpel-grammar.yml    --start_uuid 019ed224-2866-7db3-9648-196a3451d42a --stop_uuid 019ed224-2866-7db3-9648-196a3451d42a
```

* **Execute an Uncapped Bounded Range Wipe:**

```bash
# Resets safety dials for every record chronologically following the target boundary
./run.sh pipeline/25-scalpel-safety-dials.yml --start_uuid 019ed0a1-3d92-7123-a70f-72d1e9093b01
```

*Once corrections are introduced, re-run `./run.sh pipeline/30-refine.yml` to automatically re-enrich only the reset files. You need to reset the health tags first using `./run.sh pipeline/35-report-records.yml --reset_health true`.*

#### 6. Execute SFT Model Training & Weight Export

```bash
# Target, merge, and bake the General Variant GGUF
./run.sh pipeline/60-train-general.yml

# Target, merge, and bake the Unbound Variant GGUF
./run.sh pipeline/61-train-unbound.yml
```

## Complete Pipeline Component Inventory

* `pipeline/10-init.yml` – Local volume allocation, partition verification, and base structural setup.
* `pipeline/20-ingest.yml` – Multi-source corpus parsing engine into matching CDM standard file trees.
* `pipeline/25-scalpel-characters.yml` – Purges character metadata mappings and identity entries.
* `pipeline/25-scalpel-safety-dials.yml` – Clears sexual, violent, and toxic alignment metrics.
* `pipeline/25-scalpel-genre-theme.yml` – Resets primary categorizations and theme arrays.
* `pipeline/25-scalpel-grammar.yml` – Resets model-transformed text runs back to their original raw source blocks.
* `pipeline/30-refine.yml` – Multi-stage contextual processing loop deploying localized inference.
* `pipeline/35-report-records.yml` – Operational telemetry suite verifying data schemas and statistical weights.
* `pipeline/60-train-general.yml` – Supervised Fine-Tuning execution, 16-bit parameter fusion, and distribution quantification for the General flavor.
* `pipeline/61-train-unbound.yml` – SFT optimization, weight fusion, and quantization for the abliterated Unbound flavor.

## Operation Methodology

LilaKosha is designed around an iterative, operator-driven refinement workflow rather than a single linear execution. The dataset evolves through repeated inspection, targeted intervention, and re-processing until the corpus reaches the desired quality threshold for training.

### Phase 1 — Initialize

Initialize the workspace and ingest the source corpus only once for a new dataset.

```bash
./run.sh pipeline/10-init.yml
./run.sh pipeline/20-ingest.yml
```

This establishes the Common Data Model (CDM) records that become the authoritative working set for all subsequent operations. Update the `limit` in the `20-ingest.yml` to include more records as it gets progressively built.

### Phase 2 — Execute a Refinement Campaign

Refinement campaigns are executed using a dedicated pipeline manifest.

For routine work, use the current refinement pipeline:

```bash
./run.sh pipeline/30-refine.yml
```

IMPORTANT: create a timestamped copy of the pipeline (for example `20260701103000-refine.yml`), document the intent within the manifest, and execute that specific pipeline instead.

Timestamped pipeline manifests provide a reproducible operational history of dataset evolution and should generally be treated as immutable after execution.

### Phase 2.5 — Document the Campaign

Each refinement campaign should capture its intent within the pipeline manifest through comments describing:

* The objective of the campaign.
* Any prompt or model changes being evaluated.
* Expected outcomes.
* Operator notes or observations.

The manifest becomes both the executable configuration and the permanent record of that refinement effort.

### Phase 3 — Monitor Progress

While refinement is running, continuously monitor dataset health using the live dashboard.

```bash
./watch-cdm.sh
```

This performs a read-only audit of the dataset without modifying any records, allowing the operator to observe progress in real time.

### Phase 4 — Investigate Anomalies

When telemetry reports defective or suspicious records, inspect the affected data before making changes.

For example, character identity mappings can be reviewed using:

```bash
./inspect-char-names.sh
```

Additional inspection utilities may be introduced over time following the same pattern.

### Phase 5 — Perform Surgical Repairs

When defects are isolated to a specific refinement stage, execute the appropriate Scalpel pipeline to clear only the affected metadata.

Examples include:

* Character extraction
* Grammar normalization
* Genre and theme classification
* Safety dial annotation

Scalpel operations intentionally preserve all unrelated refinements, minimizing unnecessary recomputation.

### Phase 6 — Re-run the Refinement Campaign

After a Scalpel intervention, Re-execute the same pipeline manifest that originally performed the refinement. This preserves the exact prompts, models, parameters, and operator notes associated with that refinement campaign.

The refinement engine automatically skips completed work and regenerates only the cleared sections, allowing iterative correction with minimal processing overhead.

### Phase 7 — Validate the Dataset

Once refinement is complete, execute the reporting pipeline without audit mode to persist authoritative health classifications.

Only datasets that satisfy the desired quality criteria should proceed to preparation and training.

### Phase 8 — Prepare and Train

After the dataset has been validated, execute the preparation and training pipelines.

```bash
./run.sh pipeline/40-prepare.yml

./run.sh pipeline/60-train-general.yml
# or
./run.sh pipeline/61-train-unbound.yml
```

Training should always be performed against a validated dataset whose refinement history is documented by the corresponding pipeline manifest.
