# Provenance model

NistChemData is intended to document how selected local working files can be
reconstructed from the NIST Chemistry WebBook / SRD 69 using NistChemPy.

The cleaned public repository does not include generated WebBook-derived data
files. The tables below describe local artifacts that scripts may generate on a
user's machine.

## General principles

- Generated files are local working artifacts and are ignored by Git.
- Generated files may be derived from NIST Chemistry WebBook / SRD 69 and from
  source-literature-origin collections exposed through WebBook records.
- The repository MIT license applies only to original scripts and documentation.
- Generated files should be accompanied by lightweight manifests where practical.
- Manifests record what was attempted, what was written, and which source section
  or URL was used; they do not grant reuse rights.

## Planned local artifacts

| Local artifact | Script | Source/provenance | Repository status |
|---|---|---|---|
| `local-data/raw/spectra/nist_IR.zip` | `scripts/download_spectra.py IR` | WebBook IR section / JDX downloads | Generated locally, not committed |
| `local-data/raw/spectra/nist_TZ.zip` | `scripts/download_spectra.py TZ` | WebBook THz IR section / JDX downloads | Generated locally, not committed |
| `local-data/raw/spectra/nist_MS.zip` | `scripts/download_spectra.py MS` | WebBook electron-ionization MS section / JDX downloads | Generated locally, not committed |
| `local-data/raw/spectra/nist_UV.zip` | `scripts/download_spectra.py UV` | WebBook UV/Visible section / JDX downloads | Generated locally, not committed |
| `local-data/processed/nist_ms.jsonl` | `scripts/process_ms_spectra.py` | Derived from local `nist_MS.zip`; JSON output is also supported | Generated locally, not committed |
| `local-data/processed/nist_ir_info.csv` | `scripts/process_ir_spectra.py` | Derived from local `nist_IR.zip` JDX headers | Generated locally, not committed |
| `local-data/raw/mol3d/nist_mol3D_raw_mol.zip` | `scripts/download_mol3D.py` | WebBook 3D MOL/SDF links | Generated locally, not committed |
| `local-data/processed/nist_mol3D.sdf` | `scripts/download_mol3D.py` | Derived from local raw MOL archive | Generated locally, not committed |
| `local-data/processed/nist_mol3D.zip` | `scripts/download_mol3D.py` | Archive of generated local SDF | Generated locally, not committed |
| `local-data/raw/gc/nist_gc_parts.zip` | `scripts/download_gas_chromatography.py` | WebBook gas-chromatography retention-index pages | Generated locally, not committed |
| `local-data/processed/nist_gc.csv` | `scripts/download_gas_chromatography.py` | Combined table derived from local GC part files | Generated locally, not committed |
| `local-data/processed/nist_gc.zip` | `scripts/download_gas_chromatography.py` | Archive of generated local GC table | Generated locally, not committed |

## Manifests

Large local workflows should write simple CSV manifests under
`local-data/manifests/`. A manifest is a local processing ledger, not a license.
It helps users resume downloads, inspect failures, and trace generated files back
to source sections or URLs.

Typical manifest columns:

```text
compound_id,data_type,status,n_files,archive_members,source_url,message
```

Optional columns may include retrieval time, script name, or conservative rights
status labels such as `SRD_DERIVED_REUSE_NOT_CONFIRMED`.

## Future NistChemPy integration

Current scripts may use the packaged NistChemPy WebBook index as a temporary
compatibility layer. After NistChemPy moves this index to a local user-generated
cache, NistChemData should switch to that cache through a small adapter in
`scripts/common.py`.
