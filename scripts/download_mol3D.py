'''Downloads NIST Chemistry WebBook 3D MOL-files'''

#%% Imports

import os, argparse, time

import requests

from tqdm import tqdm

from rdkit import Chem
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*') 

import nistchempy as nist


#%% Functions

def download_mol3D(dir_mol: str, crawl_delay: float = 5) -> None:
    '''Downloads available WebBook's 3D MOL-files
    
    Arguments:
        dir_mol (str): directory for downloading MOL-files
        crawl_delay (float): interval between HTTP requests in seconds
    
    '''
    
    # get IDs
    df = nist.get_all_data()
    df = df.loc[~df.mol3D.isna(), ['ID', 'mol3D']]
    # drop downloaded ones
    loaded = [f.replace('.mol', '') for f in os.listdir(dir_mol) if '.mol' in f]
    df = df.loc[~df.ID.isin(loaded)]
    
    # download files
    for ID, url in tqdm(zip(df.ID, df.mol3D), total = len(df)):
        time.sleep(crawl_delay)
        try:
            r = requests.get(url)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            tqdm.write(f'{ID}: error while getting response')
            continue
        # errors
        if not r.ok:
            tqdm.write(f'{ID}: {r.status_code} status code')
            continue
        if not r.text.strip():
            tqdm.write(f'{ID}: empty file')
            continue
        # save text
        path_mol = os.path.join(dir_mol, f'{ID}.mol')
        with open(path_mol, 'w') as outf:
            outf.write(r.text.replace('\r\n', '\n'))
    
    return


def save_sdf(dir_mol: str, path_sdf: str) -> None:
    '''Transforms downloaded MOL-files to SDF format
    
    Arguments:
        dir_mol (str): directory for downloading MOL-files
        path_sdf (str): path to save output SDF file
    
    '''
    text = []
    bad = []
    
    # check molfiles
    fs = [os.path.join(dir_mol, f) for f in os.listdir(dir_mol)]
    for f in tqdm(fs, total = len(fs)):
        mol = Chem.MolFromMolFile(f, removeHs = False, sanitize = False, strictParsing = False)
        if not mol:
            bad.append(f)
    print(f'{len(bad)} bad files detected')
    
    # get molfile texts
    fs = [f for f in fs if f not in bad]
    for f in tqdm(fs, total = len(fs)):
        with open(f, 'r') as inpf:
            add = inpf.read()
        text.append(add)
    
    # save sdf
    with open(path_sdf, 'w') as outf:
        outf.write(''.join(text))
    
    return



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
    '''Checks script arguments
    
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
    '''Downloads 3D MOL-files and saves them as SDF-file'''
    
    # prepare arguments
    args = get_arguments()
    check_arguments(args)
    
    # download
    print('\nDownloading 3D MOL-files ...')
    download_mol3D(args.dir_mol, args.crawl_delay)
    
    # save sdf
    print('\nGenerating SDF ...')
    save_sdf(args.dir_mol, args.path_sdf)
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


