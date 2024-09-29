'''Downloads NIST Chemistry WebBook 3D MOL-files'''

#%% Imports

import os, argparse, time

from tqdm import tqdm

from rdkit import Chem

import nistchempy as nist


#%% Functions






#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Downloads all available NIST Chemistry WebBook 3D MOL-files')
    parser.add_argument('dir_mol', help = 'directory to save downloaded MOL-files')
    parser.add_argument('path_sdf', help = 'output sdf file')
    parser.add_argument('--crawl-delay', type = float, default = 5,
                        help = 'pause between HTTP requests, seconds')
    args = parser.parse_args()
    
    return args


def check_arguments(args: argparse.Namespace) -> None:
    '''Tries to create dir_data if it does not exist and raizes error if dir_data is a file
    
    Arguments:
        args (argparse.Namespace): input parameters
    
    '''
    # check mol dir
    if not os.path.exists(args.dir_mol):
        os.mkdir(args.dir_mol) # FilexExistsError / FileNotFoundError
    if not os.path.isdir(args.dir_mol):
        raise ValueError(f'Given dir_mol argument is not a directory: {args.dir_mol}')
    # check output dir
    dir_out = os.path.dirname(args.path_sdf)
    if not os.path.isdir(dir_out):
        raise ValueError(f'Directory of the path_sdf does not exist: {args.path_sdf}')
    # crawl delay
    if args.crawl_delay < 0:
        raise ValueError(f'--crawl-delay must be positive: {args.crawl_delay}')
    
    return


def main() -> None:
    '''Extracts info on NIST Chemistry WebBook compounds and saves to csv file'''
    
    # prepare arguments
    args = get_arguments()
    check_arguments(args)
    
    # download spectra
    print()
    
    print()
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


