'''Transforms raw MS spectra to the ready-to-go JSON format'''

#%% Imports

import re, os, argparse, zipfile, json

import pandas as pd

from tqdm import tqdm

from typing import Tuple, List


#%% Functions

def jdx_text_to_spectra(text: str) -> Tuple[List[int], List[int]]:
    '''Extracts MS spectra from the text block of JDX file
    
    Arguments:
        text (str): text of JDX file
    
    Returns:
        Tuple[List[int], List[int]]: m/z and intensity lists ordered by m/z
    
    '''
    MS = re.search(r'(\d+,\d+\s+)+', text).group(0).replace('\n', ' ').strip()
    MS = [(int(k), int(v)) for k, v in [p.split(',') for p in MS.split()]]
    mz, intens = zip(*sorted(MS))
    mz, intens = list(mz), list(intens)
    
    return mz, intens


def process_ms_spectra(path_zip: str, path_comp: str, path_out: str) -> None:
    '''Processes MS spectra and saves them to csv file
    
    Arguments:
        path_zip (str): zip-file containing raw MS spectra
        path_comp (str): path to compounds.csv file
        path_out (str): output csv file
    
    '''
    # prepare names and inchis
    main = pd.read_csv(path_comp)
    main = main[['ID', 'name', 'inchi']]
    main = main.set_index('ID')
    
    # output
    data = []
    
    # prepare ZIP
    with zipfile.ZipFile(path_zip, 'r') as zipf:
        # iterate files
        for f in tqdm(zipf.filelist, total = len(zipf.filelist)):
            if f.is_dir():
                continue
            # treat the first spectrum for each compound
            ID, spec_type, idx = os.path.basename(f.filename).replace('.jdx', '').split('_')
            if idx != '0':
                continue
            # read file
            text = zipf.read(f).decode()
            mz, intens = jdx_text_to_spectra(text)
            item = {'ID': ID, 'name': main.loc[ID, 'name'],
                    'inchi': main.loc[ID, 'inchi'], 'mz': mz,
                    'intensities': intens}
            data.append(item)
    
    # save JSON
    with open(path_out, 'w') as outf:
        json.dump(data, outf, indent = 0)
    
    return


#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Transforms raw MS spectra to the JSON format')
    parser.add_argument('path_zip', help = 'zip-file containing raw MS spectra')
    parser.add_argument('path_comp', help = 'compounds.csv')
    parser.add_argument('path_out', help = 'output JSON file')
    args = parser.parse_args()
    
    return args


def check_arguments(args: argparse.Namespace) -> None:
    '''Checks path arguments
    
    Arguments:
        args (argparse.Namespace): input parameters
    
    '''
    # check zip
    if not os.path.exists(args.path_zip):
        raise ValueError(f'Given path_zip argument does not exist: {args.path_zip}')
    # check compounds.csv
    if not os.path.exists(args.path_comp):
        raise ValueError(f'Given path_comp argument does not exist: {args.path_comp}')
    # check output path
    dir_out = os.path.dirname(args.path_out)
    if not os.path.isdir(dir_out):
        raise ValueError(f'Output directory does not exist: {args.path_out}')
    
    return


def main() -> None:
    '''Processes MS spectra and saves them to json file'''
    
    # prepare arguments
    args = get_arguments()
    check_arguments(args)
    
    # process spectra
    print('\nProcessing MS spectra ...')
    process_ms_spectra(args.path_zip, args.path_comp, args.path_out)
    print()
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


