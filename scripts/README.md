# NistChemData scripts

This directory contains scripts for reconstructing selected local working files
from the NIST Chemistry WebBook / SRD 69 using NistChemPy.

The scripts are provided for local reproducibility and source tracking.
Generated files may be derived from NIST Standard Reference Data and/or
source-literature-origin collections exposed through WebBook records. Generated
files are not covered by the repository MIT license and should not be committed
to this repository.

Read the repository-level [DATA_NOTICE.md](../DATA_NOTICE.md) before running the
scripts.

## Requirements

Install the core script requirements from:

```bash
pip install -r scripts/requirements.txt
```

The requirements use the NistChemPy 2.0 development/release line. That line
loads WebBook metadata from a user-local index instead of a packaged index. If
2.0 is not published yet, install NistChemPy from the sibling repository before
running these scripts.

Build or import a local NistChemPy index before running download or processing
commands that need compound metadata or section availability:

```bash
nistchempy index path
nistchempy index build --path ./webbook-index --accept-data-terms
nistchempy index status --path ./webbook-index
```

Scripts use NistChemPy's default index path, including `NISTCHEMPY_INDEX_PATH`,
unless an explicit `--index-path` is passed. For example:

```bash
python scripts/download_spectra.py IR \
  --index-path ./webbook-index \
  --limit 5 \
  --accept-data-terms
```

Optional RDKit validation for `process_mol3D.py --validate` requires RDKit. If
pip installation is suitable for your platform, you can install the optional
requirements from:

```bash
pip install -r scripts/requirements-rdkit.txt
```

If RDKit installation through pip is problematic, install RDKit from conda-forge
and run the scripts from that environment instead. RDKit is not required for the
default mol3D assembly workflow.

## Local output layout

The cleaned repository does not include generated data. Recommended local output
paths are:

```text
local-data/
  raw/
    spectra/
      nist_IR.zip
      nist_TZ.zip
      nist_MS.zip
      nist_UV.zip
    nist_mol3D_raw.zip
    nist_gc_parts.zip
  processed/
    nist_ms.jsonl
    nist_ir_info.csv
    nist_mol3D.sdf
    nist_mol3D.zip
    nist_gc.csv
    nist_gc.zip
  manifests/
```

These paths are ignored by Git. Download scripts write manifests under
`local-data/manifests/`; processing scripts operate on local inputs and do not
write manifests by default.

## Current scripts

### `download_spectra.py`

`download_spectra.py` downloads local raw JDX archives for IR, THz IR, mass,
and UV/Visible spectra. It writes directly to a local ZIP archive and records a
small CSV manifest for restart/provenance checks.

Example:

```bash
python scripts/download_spectra.py MS \
  --out local-data/raw/spectra/nist_MS.zip \
  --manifest local-data/manifests/nist_MS_manifest.csv \
  --crawl-delay 1.0 \
  --timeout 30 \
  --max-attempts 3 \
  --accept-data-terms
```

For a small test run, use `--limit` or `--ids`:

```bash
python scripts/download_spectra.py IR --limit 5 --accept-data-terms
```

Resume behavior uses both the manifest and the ZIP archive. By default, a
compound is skipped if the latest manifest row is a valid `done` row or, when no
manifest row exists for that compound, if the archive already contains non-empty
matching JDX files, including files stored under a legacy top-level folder such
as `TZ/B7000012_TZ_0.jdx`. If the latest manifest row is `error`, `no_data`, or
an invalid `done` row, the compound is checked again. To scan source pages and
repair potentially missing spectrum indexes without re-downloading existing JDX
files, use:

```bash
python scripts/download_spectra.py TZ \
  --out local-data/raw/spectra/nist_TZ.zip \
  --verify-existing-archive \
  --accept-data-terms
```

### `process_ms_spectra.py`

`process_ms_spectra.py` converts a local raw MS JDX archive into a local JSONL
peak-list file by default. By default, it processes one spectrum per compound,
preserving the previous record shape as one JSON object per line. Use
`--spectrum-policy all` if you want every MS JDX member represented in the
output. Since processing uses a local archive, it does not write a manifest;
parsing errors abort the run with the failing archive member name. A JSON array
can still be written with `--format json` or a `.json` output suffix.

Example:

```bash
python scripts/process_ms_spectra.py \
  local-data/raw/spectra/nist_MS.zip \
  local-data/processed/nist_ms.jsonl \
  --accept-data-terms
```

### `process_ir_spectra.py`

`process_ir_spectra.py` extracts metadata from a local raw IR JDX archive into a
local CSV table. It uses the NistChemPy index for compound names and InChI
strings, so it no longer requires the historical `data/nist_compounds.csv` file.
Since processing uses a local archive, it does not write a manifest; parsing
errors abort the run with the failing archive member name.

Example:

```bash
python scripts/process_ir_spectra.py \
  local-data/raw/spectra/nist_IR.zip \
  local-data/processed/nist_ir_info.csv \
  --accept-data-terms
```

For a small test run, use `--limit` or `--ids`:

```bash
python scripts/process_ir_spectra.py --limit 10 --accept-data-terms
```

### `download_mol3D.py`

`download_mol3D.py` downloads available WebBook 3D structure records into a
local raw MOL ZIP archive. The ZIP members use the legacy-compatible root-level
name pattern `{ID}.mol`. Resume behavior uses both the manifest and existing
non-empty MOL archive members. Archive-only state is trusted only for compounds
with no manifest row; a latest `error`, `no_data`, or invalid `done` row triggers
a repair attempt.

Example:

```bash
python scripts/download_mol3D.py \
  --out local-data/raw/nist_mol3D_raw.zip \
  --manifest local-data/manifests/nist_mol3D_manifest.csv \
  --crawl-delay 1.0 \
  --timeout 30 \
  --max-attempts 3 \
  --accept-data-terms
```

For a small test run, use `--limit` or `--ids`:

```bash
python scripts/download_mol3D.py --limit 5 --accept-data-terms
```

### `process_mol3D.py`

`process_mol3D.py` assembles a local raw MOL ZIP archive into a single local SDF
file. It preserves the downloaded records as text and does not rewrite
structures through RDKit by default. Optional RDKit validation is available with
`--validate`. Since processing uses a local archive, it does not write a
manifest; parsing or validation errors abort the run with the failing member
name.

Example:

```bash
python scripts/process_mol3D.py \
  local-data/raw/nist_mol3D_raw.zip \
  local-data/processed/nist_mol3D.sdf \
  --zip-output local-data/processed/nist_mol3D.zip \
  --accept-data-terms
```

### `download_gas_chromatography.py`

`download_gas_chromatography.py` downloads available WebBook gas-chromatography
retention-index tables into a local raw CSV-parts ZIP archive. The ZIP members
use the historical filename convention:

```text
{ID}_{Retention index type}_{Column polarity}_{Temperature regime}.csv
```

For example:

```text
R32777_Kovats' RI_non-polar column_isothermal.csv
```

This means old loose GC CSV files can usually be repacked into the raw ZIP and
reused without re-downloading. Archive-only state is trusted only for compounds
with no manifest row; a latest `error`, `no_data`, or invalid `done` row triggers
a repair attempt. Use `--verify-existing-archive` to scan WebBook source pages
and download only missing table parts.

Example:

```bash
python scripts/download_gas_chromatography.py \
  --out local-data/raw/nist_gc_parts.zip \
  --manifest local-data/manifests/nist_gc_manifest.csv \
  --crawl-delay 1.0 \
  --timeout 30 \
  --max-attempts 3 \
  --accept-data-terms
```

### `process_gas_chromatography.py`

`process_gas_chromatography.py` combines a local raw GC-parts ZIP archive into a
single local CSV table and, optionally, a ZIP archive containing that table. It
adds compound names and InChI strings from the NistChemPy index and derives GC
metadata from the old-compatible raw part filenames. Since processing uses a
local archive, it does not write a manifest; unreadable or badly named raw parts
abort the run with the failing member name.

Example:

```bash
python scripts/process_gas_chromatography.py \
  local-data/raw/nist_gc_parts.zip \
  local-data/processed/nist_gc.csv \
  --zip-output local-data/processed/nist_gc.zip \
  --accept-data-terms
```
