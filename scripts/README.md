# NistChemData scripts

The directory contains scripts used to extract and prepare the NIST Chemistry WebBook data presented in this repository.


## Requirements

All requirements are listed in [requirements.txt](requirements.txt).

**tqdm** is the only addition to **NistChemPy** and its dependences.


## Scripts

1. [download_spectra.py](download_spectra.py): downloads raw IR, TZ, MS, and UV spectra ([raw spectra](../data/raw_spectra/)). List of WebBook compounds is prepared using pre-saved data of the **NistChemPy** package.

2. [process_ms_spectra.py](process_ms_spectra.py): transforms raw MS spectra to the ready-to-go JSON-format ([nist_ms.json](../data/nist_ms.json)).

3. [download_mol3D.py](download_mol3D.py): downloads 3D MOL-files and transforms them into single SDF-file ([nist_mol3D.sdf](../data/nist_mol3D.sdf)).

