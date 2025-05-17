'''Extracts meta-info from JDX files and saves them in tabular format'''

#%% Imports

import re, os, argparse

import pandas as pd

from tqdm import tqdm


#%% Functions




def process_ir_spectra(dir_jdx: str) -> pd.core.frame.DataFrame | None:
    '''Reads JDX-formatted IR spectra from the given directory,
    processes them, and returns tabular-formatted info
    
    Arguments:
        dir_jdx (str): path to the directory containing IR spectra
    
    Returns:
        pd.core.frame.DataFrame: table containing meta-info on IR spectra
    
    '''
    
    return None


#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Extracts meta-info from JDX-formatted IR spectra and saves it as CSV-file')
    parser.add_argument('dir_jdx', help = 'Directory containing JDX-formatted IR spectra')
    parser.add_argument('path_out', help = 'Output CSV file')
    args = parser.parse_args()
    
    return args


def check_arguments(args: argparse.Namespace) -> None:
    '''Checks path arguments
    
    Arguments:
        args (argparse.Namespace): input parameters
    
    '''
    # check zip
    if not os.path.isdir(args.dir_jdx):
        raise ValueError(f'Given dir_jdx directory does not exist: {args.dir_jdx}')
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
    print('\nProcessing IR spectra ...')
    df = process_ir_spectra(args.dir_jdx)
    if df is not None:
        df.to_csv(args.path_out)
    print()
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


