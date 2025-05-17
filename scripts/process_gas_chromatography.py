'''Transforms raw GC data to the ready-to-go CSV-file'''

#%% Imports

import os, argparse, zipfile

import pandas as pd

from tqdm import tqdm


#%% Functions

def process_gas_chromatography(path_zip: str, path_comp: str, path_out: str) -> None:
    '''Processes raw GC data and saves it to csv file
    
    Arguments:
        path_zip (str): zip-file containing raw GC data
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
            # read file
            text = zipf.read(f).decode()
            pass
    
    # save JSON
    data = pd.DataFrame(data)
    data.to_csv(path_out, index = None)
    
    return


#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Transforms raw GC data to the CSV-file')
    parser.add_argument('path_zip', help = 'zip-file containing raw GC data')
    parser.add_argument('path_comp', help = 'path to the compounds.csv file')
    parser.add_argument('path_out', help = 'path to the output JSON file')
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
    '''Processes GC data and saves it to CSV-file'''
    
    # prepare arguments
    args = get_arguments()
    check_arguments(args)
    
    # process spectra
    print('\nProcessing GC data ...')
    process_gas_chromatography(args.path_zip, args.path_comp, args.path_out)
    print()
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


