# NistChemData scripts

This directory contains scripts for reconstructing selected local working files
from the NIST Chemistry WebBook / SRD 69 using NistChemPy.

The scripts are provided for local reproducibility and provenance inspection.
Generated files may be derived from NIST Standard Reference Data and/or
source-literature-origin collections exposed through WebBook records. Generated
files are not covered by the repository MIT license and should not be committed
to this repository.

Read the repository-level [DATA_NOTICE.md](../DATA_NOTICE.md) before running the
scripts.

## Requirements

Install the script requirements from:

```bash
pip install -r scripts/requirements.txt
```

Some workflows may require additional optional dependencies. For example, the
3D-structure workflow may use RDKit for validation.

## Local output layout

The cleaned repository does not include generated data. Recommended local output
paths are:

```text
local-data/
  raw/
    spectra/
    mol3d/
    gc/
  processed/
  manifests/
```

These paths are ignored by Git.

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

### Remaining scripts

The remaining scripts are still being migrated from the earlier data-repository
workflow to the local reconstruction workflow:

- `process_ir_spectra.py` extracts metadata from a local raw IR JDX archive.
- `download_mol3D.py` downloads local 3D MOL files and can assemble a local SDF
  archive.
- `download_gas_chromatography.py` downloads local gas-chromatography retention
  index tables and can assemble a local combined table.

Future updates will migrate download scripts to the same explicit local-output,
manifest, and data-scope acknowledgement pattern. Processing scripts will use
plain success/failure behavior because they operate on local inputs.
