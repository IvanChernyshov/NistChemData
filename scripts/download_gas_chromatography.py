'''Downloads NIST Chemistry WebBook data on gas chromatography'''

#%% Imports

import os, sys, argparse

from tqdm import tqdm

import nistchempy as nist


#%% Functions

def download_gas_chromatography(dir_out: str, crawl_delay: float = 1,
                                timeout: float = 30) -> None:
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



#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Downloads all available NIST Chemistry WebBook spectra of the given type')
    parser.add_argument('dir_out', help = 'directory to save downloaded spectra')
    parser.add_argument('--crawl-delay', type = float, default = 1.0,
                        help = 'pause between HTTP requests, seconds')
    parser.add_argument('--timeout', type = float, default = 30.0,
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
    
    # download spectra
    print('\nDownloading GC data ...')
    download_gas_chromatography(args.dir_out, args.crawl_delay, args.timeout)
    print()
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


