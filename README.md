# NistChemData: Extracted Physico-Chemical Data from NIST Chemistry WebBook

**NistChemData** is a repository for physico-chemical data extracted from the [NIST Chemistry WebBook](https://webbook.nist.gov/). 

Currently, it includes spectral data, such as IR, THz IR, MS, and UV-Vis.

Data extraction was carried out using the [NistChemPy](https://github.com/IvanChernyshov/NistChemPy) package. For more details, please refer to the [scripts/](scripts/) directory.

As **NistChemPy** continues to evolve and enhance its extraction capabilities, we will incorporate additional thermodynamic and spectral data into this repository.

The scripts used to extract and prepare the data presented in this repository are located in the [scripts/](scripts/) folder.


## Data Cookbook

### [Compounds](data/compounds.csv)

A tabular list of compounds from the NIST Chemistry WebBook, including the following parameters:

- *ID* (str): NIST Chemistry WebBook Compound ID;

- *name* (str): chemical name;

- *synonyms* (str): alternative chemical names, separated by "\n";

- *formula* (str): chemical formula;

- *cas_rn* (str): CAS Registry Number;

- *mol_weight* (float): molar weight, g/mol;

- *inchi* (str): InChI string;

- *inchi_key* (str): InChI Key string.


### [Spectra](data/spectra/)

1. [Raw spectra](data/spectra/init): contains JDX-formatted IR, THz, MS, and UV-Vis spectra. Spectra are organized by type and archived in zip files. 

    - File naming convention: {NIST Compound ID}\_{Spectrum Type}\_{Spectrum Index}.

2. [Processed MS data](data/spectra/ms.csv): contains information on electron ionization mass spectrometry (MS) spectra, including the following fields:

    - *ID* / *name* / *inchi* (str): same as in [compounds.csv](data/compounds.csv);
    
    - *"14"* ... *"279"* (int): relative intensities (normalized to 9999) of peacks with m/z values ranging from 0 to 279 Da.

