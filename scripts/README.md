# NistChemData scripts

The directory contains scripts used to extract and prepare the NIST Chemistry WebBook data presented in this repository.


## Requirements

All requirements are listed in [requirements.txt](requirements.txt).

**tqdm** is the only addition to **NistChemPy** and its dependences.


## Scripts

1. [download_spectra.py](download_spectra.py): downloads IR, TZ, MS, and UV spectra. List of WebBook compounds is prepared using pre-saved data of the **NistChemPy** package.

2. [process_ms_spectra.py](process_ms_spectra.py): transforms raw MS spectra to the ready-to-go csv-format.

