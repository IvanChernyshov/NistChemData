'''Transforms raw MS spectra to the ready-to-go tabular format'''

#%% Imports

import re, os, argparse, zipfile

import pandas as pd

from tqdm import tqdm

from typing import Dict


#%% Functions

def jdx_text_to_spectra(text: str) -> Dict[int, int]:
    '''Extracts MS spectra from the text block of JDX file
    
    Arguments:
        text (str): text of JDX file
    
    Returns:
        Dict[int, int]: m/z => intensity dictionary
    
    '''
    MS = re.search(r'(\d+,\d+\s+)+', text).group(0).replace('\n', ' ').strip()
    MS = {int(k): int(v) for k, v in [p.split(',') for p in MS.split()]}
    
    return MS


def dict_to_array(spec: Dict[int, int], mz_min: int, mz_max: int) -> Dict[str, int]:
    '''Transforms m/z=>intensity dict to continuous col=>int dict
    
    Arguments:
        spec (Dict[int, int]): m/z => intensity
        mz_min (int): minimal m/z value
        mz_max (int): maximal m/z value
    
    Returns:
        Dict[str, int]: f"mz{m/z}" => intensity for each m/z between min & max
    
    '''
    outp = {f'{mz}': 0 for mz in range(mz_min, mz_max + 1)}
    for mz, intensity in spec.items():
        outp[f'{mz}'] = intensity
    
    return outp


def process_ms_spectra(path_zip: str, path_comp: str, path_out: str) -> None:
    '''Processes MS spectra and saves them to csv file
    
    Arguments:
        path_zip (str): zip-file containing raw MS spectra
        path_comp (str): path to compounds.csv file
        path_out (str): output csv file
    
    '''
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
            MS = jdx_text_to_spectra(text)
            data.append( (ID, MS) )
    
    # get min and max m/z
    mz_min, mz_max = float('inf'), 0
    for ID, MS in data:
        mz_min = min(mz_min, min(MS))
        mz_max = max(mz_max, max(MS))
    
    # prepare dataframe
    main = pd.read_csv(path_comp)
    main = main[['ID', 'name', 'inchi']]
    df = [{'ID': ID, **dict_to_array(MS, mz_min, mz_max)} for ID, MS in data]
    df = pd.DataFrame(df)
    df = main.merge(df, on = 'ID', how = 'right')
    df = df.sort_values('ID', ignore_index = True)
    
    # save dataframe
    df.to_csv(path_out, index = None)
    
    return


#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Transforms raw MS spectra to the tabular format')
    parser.add_argument('path_zip', help = 'zip-file containing raw MS spectra')
    parser.add_argument('path_comp', help = 'compounds.csv')
    parser.add_argument('path_out', help = 'output csv file')
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
    '''Processes MS spectra and saves them to csv file'''
    
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


