# NistChemData scripts

The directory contains scripts used to extract and prepare the NIST Chemistry WebBook data presented in this repository.


## Requirements

All requirements are listed in [requirements.txt](requirements.txt).

**tqdm** is the only addition to **NistChemPy** and its dependences.


## Scripts

1. [download_spectra.py](download_spectra.py): downloads raw IR, TZ, MS, and UV spectra ([raw spectra](../data/spectra/init)). List of WebBook compounds is prepared using pre-saved data of the **NistChemPy** package.

2. [process_ms_spectra.py](process_ms_spectra.py): transforms raw MS spectra to the ready-to-go csv-format ([ms.csv](../data/ms.csv)).

3. [download_mol3D.py](download_mol3D.py): downloads 3D MOL-files and transforms them into single SDF-file ([mol3D.sdf](../data/mol3D.sdf)).

