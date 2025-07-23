# NistChemData: Extracted Physico-Chemical Data from NIST Chemistry WebBook

**NistChemData** is a repository for physico-chemical data extracted from the [NIST Chemistry WebBook](https://webbook.nist.gov/). 

Currently, it includes spectral (IR, THz IR, MS, UV-Vis) and quantum chemical data (3D atomic coordinates, simulated IR spectra, etc.).

Data extraction was carried out using the [NistChemPy](https://github.com/IvanChernyshov/NistChemPy) package. For more details, please refer to the [scripts/](scripts/) directory.

As **NistChemPy** continues to evolve and enhance its extraction capabilities, we will incorporate additional thermodynamic and spectral data into this repository.

The scripts used to extract and prepare the data presented in this repository are located in the [scripts/](scripts/) folder.


## Data Cookbook

### [Compounds](data/nist_compounds.csv)

A tabular list of 144795 compounds from the NIST Chemistry WebBook, including the following parameters:

- `ID` (str): NIST Chemistry WebBook Compound ID;

- `name` (str): chemical name;

- `synonyms` (str): alternative chemical names, separated by "\n";

- `formula` (str): chemical formula;

- `cas_rn` (str): CAS Registry Number;

- `mol_weight` (float): molar weight, g/mol;

- `inchi` (str): InChI string;

- `inchi_key` (str): InChI Key string.


### [3D atomic coordinates & QC properties](data/nist_mol3D.zip)

SDF-file containing 3D atomic coordinates for 54477 WebBook compounds along with the following computed properties:

- `WEBBOOK.ID`: NIST Chemistry WebBook Compound ID;

- `METHOD`: quantum chemical approximation used for the computations;

- `DIPOLE.MOMENT`: dipole moment;

- `ELECTRONIC.ENERGY`: absolute electronic energy;

- `IR.FREQUENCIES`: computed frequencies and their IR intensities;

- `ROTATIONAL.CONSTANTS`: rotational constants.


### [Spectra](data/spectra/)

1. [Raw spectra](data/spectra/raw/): contains JDX-formatted IR, THz, MS, and UV-Vis spectra. Spectra are organized by type and archived in zip files.

    - 19582 [IR spectra](data/spectra/raw/nist_IR.zip) for 15890 compounds;

    - 35 [THz spectra](data/spectra/raw/nist_TZ.zip) for 32 compounds;

    - 33285 [MS spectra](data/spectra/raw/nist_MS.zip) for 33285 compounds;

    - 3063 [UV-Vis spectra](data/spectra/raw/nist_UV.zip) for 3057 compounds;

    - File naming convention: {NIST Compound ID}\_{Spectrum Type}\_{Spectrum Index};

    - Please note that some spectra (primarily IR) of the same component may appear identical, differing only in resolution (number of points per micrometer).

2. [Processed MS data](data/spectra/nist_ms.json): contains information on electron ionization mass spectrometry (MS) spectra, including the following fields:

    - `ID` / `name` / `inchi` (str): NIST compound ID, compound's name and InChI string;

    - `mz` & `intensities` (list\[int\]): lists of m/z values and relative intensities normalized to 9999.

3. [IR spectra info](data/nist_ir_info.csv): contains information on IR spectra, including the following fields:

    - `cID` / `name` / `inchi` (str): NIST compound ID, compound's name and InChI string;

    - `mp` / `bp` / `state` (str): compound's melting point, boiling points and state in the experiment (`solid`, `liquid`, `solution`, `gas`);

    - `sID` / `filename` (str): spectrum's ID and filename ([nist_IR.zip](data/spectra/raw/nist_IR.zip));

    - other columns containing info on spectrum origin.


### [Gas chromatography](data/nist_gc.zip)

CSV-file containing 367134 measurements of GC retention indexes for 80042 compounds along with the following properties:

- **Main parameters**:

    - `Compound ID`: NIST Chemistry WebBook Compound ID;

    - `Compound name`: name of the compound;

    - `InChI`: InChI string of the compound;

    - `Retention index type`: Lee's, Kovats, normal alkane, etc.;

    - `Column polarity`: polar / non-polar;

    - `Active phase`: commercial names or chemical composition;

    - `Carrier gas`: mobile phase (H2, He, Ne, etc.);

    - `Temperature regime`: isothermal / temperature ramp / custom;

    - `I`: measured retention index;

- **Details of temperature regime**:

    - Isothermal:

        - `Temperature (C)`: experimental temperature.

    - Temperature ramp:

        - `Tstart (C)`: initial temperature;

        - `Tend (C)`: final temperature;

        - `Heat rate (K/min)`;

        - `Initial hold (min)`;

        - `Final hold (min)`.

    - Custom:

        - `Program`: schematic text description of temperature-time dependence.

- **Experimental setup**:

    - `Column type`: capillary / packed / other;

    - `Column length (m)`;

    - `Column diameter (mm)`;

    - `Phase thickness (μm)`;

    - `Substrate`: substrate material.

- **Service fields**:

    - `Reference`: reference to the source of data;

    - `Comment`: additional info for the data entry.


