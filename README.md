# NistChemData: Extracted Physico-Chemical Data from NIST Chemistry WebBook

**NistChemData** is a repository for physico-chemical data extracted from the [NIST Chemistry WebBook](https://webbook.nist.gov/). 

Currently, it includes spectral (IR, THz IR, MS, UV-Vis) and quantum chemical data.

Data extraction was carried out using the [NistChemPy](https://github.com/IvanChernyshov/NistChemPy) package. For more details, please refer to the [scripts/](scripts/) directory.

As **NistChemPy** continues to evolve and enhance its extraction capabilities, we will incorporate additional thermodynamic and spectral data into this repository.

The scripts used to extract and prepare the data presented in this repository are located in the [scripts/](scripts/) folder.


## Data Cookbook

### [Compounds](data/nist_compounds.csv)

A tabular list of compounds from the NIST Chemistry WebBook, including the following parameters:

- `ID` (str): NIST Chemistry WebBook Compound ID;

- `name` (str): chemical name;

- `synonyms` (str): alternative chemical names, separated by "\n";

- `formula` (str): chemical formula;

- `cas_rn` (str): CAS Registry Number;

- `mol_weight` (float): molar weight, g/mol;

- `inchi` (str): InChI string;

- `inchi_key` (str): InChI Key string.


### [3D atomic coordinates & QC properties](data/nist_mol3D.sdf)

SDF-file containing 3D atomic coordinates along with the following computed properties:

- `WEBBOOK.ID`: NIST Chemistry WebBook Compound ID.

- `METHOD`: quantum chemical approximation used for the computations.

- `DIPOLE.MOMENT`: dipole moment.

- `ELECTRONIC.ENERGY`: absolute electronic energy.

- `IR.FREQUENCIES`: computed frequencies and their IR intensities.

- `ROTATIONAL.CONSTANTS`: rotational constants.


### Spectra

1. [Raw spectra](data/raw_spectra/): contains JDX-formatted [IR](data/raw_spectra/nist_IR.zip), [THz](data/raw_spectra/nist_TZ.zip), [MS](data/raw_spectra/nist_MS.zip), and [UV-Vis](data/raw_spectra/nist_UV.zip) spectra. Spectra are organized by type and archived in zip files.

    - File naming convention: {NIST Compound ID}\_{Spectrum Type}\_{Spectrum Index}.
    
    - Please note that some spectra (primarily IR) of the same component may appear identical, differing only in resolution (number of points per micrometer).

2. [Processed MS data](data/nist_ms.json): contains information on electron ionization mass spectrometry (MS) spectra, including the following fields:

    - `ID` / `name` / `inchi` (str): same as in [nist_compounds.csv](data/nist_compounds.csv);
    
    - `mz` & `intensities` (list\[int\]): lists of m/z values and relative intensities normalized to 9999.

