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

- `download_spectra.py` downloads local raw JDX archives for IR, THz IR, mass,
  and UV/Visible spectra.
- `process_ms_spectra.py` converts a local raw MS JDX archive into a local JSON
  peak-list file.
- `process_ir_spectra.py` extracts metadata from a local raw IR JDX archive.
- `download_mol3D.py` downloads local 3D MOL files and can assemble a local SDF
  archive.
- `download_gas_chromatography.py` downloads local gas-chromatography retention
  index tables and can assemble a local combined table.

The current implementations are being migrated from the earlier data-repository
workflow to a local reconstruction workflow. Future updates will add explicit
local archive outputs, manifests, and data-scope acknowledgement flags.
