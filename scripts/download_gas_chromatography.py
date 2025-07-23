'''Downloads NIST Chemistry WebBook data on gas chromatography'''

#%% Imports

import os, sys, argparse

import pandas as pd

from tqdm import tqdm

import nistchempy as nist


#%% Functions

def download_gas_chromatography(dir_out: str, crawl_delay: float = 0.25,
                                timeout: float = 10.0) -> None:
    '''Downloads NIST Chemistry WebBook data on gas chromatography
    
    Arguments:
        dir_out (str): output directory for csv-files
        crawl_delay (float): interval between series of requests for different compounds, seconds
        timeout (float): max time to get response, seconds
    
    '''
    # get IDs to download
    df = nist.get_all_data()
    key = nist.get_search_parameters()['cGC']
    IDs = sorted(list(df.loc[~df[key].isna(), 'ID'].values))
    
    # filter already downloaded
    loaded = sorted(list(set([f.split('_')[0] for f in os.listdir(dir_out)])))
    loaded = set(loaded[:-1]) # reload the last one
    IDs = [ID for ID in IDs if ID not in loaded]
    
    # requests config
    cfg = nist.RequestConfig(delay=crawl_delay, kwargs={'timeout': timeout})
    
    # start downloading
    for ID in tqdm(IDs):
        try:
            # load compound
            X = nist.get_compound(ID, cfg)
            if not X:
                tqdm.write(f'Can not load the compound: {ID}')
                pass
            # load spectra
            X.get_gas_chromatography()
            if not X.gas_chromat:
                tqdm.write(f'No chromatograms were downloaded for the compound: {ID}')
                continue
            # save spectra
            X.save_gas_chromatography(dir_out, index=None)
        except (KeyboardInterrupt, SystemExit):
            tqdm.write('The code execution was interrupted')
            sys.exit()
        except:
            tqdm.write(f'Error while processing compound # {ID}')
    
    return


def combine_tables(dir_csv: str, path_comp: str, path_out: str) -> None:
    '''Combines downloaded GC data into one CSV file
    
    Arguments:
        dir_csv (str): directory containing GC data as multiple csv-files
        path_comp (str): path to compounds.csv file
        path_out (str): path to the output CSV-file
    
    '''
    # inchi info
    main = pd.read_csv(path_comp, low_memory=False)
    main = main[['ID', 'name', 'inchi']]
    main = main.set_index('ID')
    
    # combine data
    data = []
    for f in tqdm(os.listdir(dir_csv)):
        # get basic info
        ps = f.replace('.csv', '').split('_')
        addend = {
            'Compound ID': ps[0],
            'Compound name': main.loc[ps[0], 'name'],
            'InChI': main.loc[ps[0], 'inchi'],
            'Retention index type': ps[1],
            'Column polarity': ps[2],
            'Temperature regime': ps[3]
        }
        # load table
        path = os.path.join(dir_csv, f)
        df = pd.read_csv(path)
        # combine and save
        rows = [{**addend, **row} for row in df.to_dict('records')]
        data += rows
    # prepare dataframe
    data = pd.DataFrame(data)
    cols = [
        'Compound ID', 'Retention index type', 'Column polarity', 'Temperature regime',
        'Column type', 'Active phase', 'Column length (m)', 'Carrier gas', 'Substrate',
        'Column diameter (mm)', 'Phase thickness (μm)', 'Temperature (C)',
        'Tstart (C)', 'Tend (C)', 'Heat rate (K/min)', 'Initial hold (min)', 'Final hold (min)',
        'Program', 'I', 'Reference', 'Comment'
    ]
    data = data[cols]
    data = data.sort_values(['Compound ID', 'Column polarity', 'Active phase',
                             'Retention index type', 'Temperature regime'])
    
    # save
    data.to_csv(path_out, index=None)
    
    return



#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Downloads all available NIST Chemistry WebBook spectra of the given type')
    parser.add_argument('dir_out', help = 'directory to save downloaded GC data')
    parser.add_argument('path_comp', help = 'path to compounds.csv')
    parser.add_argument('path_csv', help = 'output file to save combined GC data')
    parser.add_argument('--crawl-delay', type = float, default = 0.25,
                        help = 'pause between HTTP requests, seconds')
    parser.add_argument('--timeout', type = float, default = 10.0,
                        help = 'max time to get response, seconds')
    args = parser.parse_args()
    
    return args


def check_arguments(args: argparse.Namespace) -> None:
    '''Checks arguments
    
    Arguments:
        args (argparse.Namespace): input parameters
    
    '''
    # check save dir
    if not os.path.exists(args.dir_out):
        os.mkdir(args.dir_out) # FilexExistsError / FileNotFoundError
    if not os.path.isdir(args.dir_out):
        raise ValueError(f'Given dir_out argument is not a directory: {args.dir_out}')
    # check output csv
    if not os.path.isdir(os.path.dirname(args.path_csv)):
        raise ValueError(f'Given path_csv file cannot be created: {args.path_csv}')
    # check compounds.csv
    if not os.path.exists(args.path_comp):
        raise ValueError(f'Given path_comp argument does not exist: {args.path_comp}')
    # crawl delay
    if args.crawl_delay < 0:
        raise ValueError(f'--crawl-delay must be positive: {args.crawl_delay}')
    # timeout
    if args.timeout <= 0:
        raise ValueError(f'--timeout must be positive: {args.timeout}')
    
    return


def main() -> None:
    '''Extracts raw GC data and saves to csv files'''
    
    # prepare arguments
    args = get_arguments()
    check_arguments(args)
    
    # download data
    print('\nDownloading GC data ...')
    download_gas_chromatography(args.dir_out, args.crawl_delay, args.timeout)
    print()
    
    # combine data
    print('Combining GC data ...')
    combine_tables(args.dir_out, args.path_comp, args.path_csv)
    print()
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


