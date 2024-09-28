'''Downloads NIST Chemistry WebBook sitemaps and extracts all compounds'''

#%% Imports

import os, argparse, time

from tqdm import tqdm

import nistchempy as nist


#%% Functions

def download_spectra(dir_out: str, spec_type: str, crawl_delay: float = 5) -> None:
    '''Downloads NIST Chemistry WebBook spectra of the given type'''
    
    # get correct column name
    key = 'c' + spec_type.upper()
    col = nist.get_search_parameters().get(key, None)
    # get correct download method
    key = 'thz' if spec_type.lower() == 'tz' else spec_type.lower()
    method = f'get_{key}_spectra'
    specs = f'{key}_specs'
    save = f'save_{key}_spectra'
    # get IDs to download
    df = nist.get_all_data()
    IDs = sorted(list(df.loc[~df[col].isna(), 'ID'].values))
    
    # filter already downloaded
    loaded = sorted(list(set([f.split('_')[0] for f in os.listdir(dir_out)])))
    loaded = set(loaded[:-1]) # reload the last one
    IDs = [ID for ID in IDs if ID not in loaded]
    
    # start downloading
    for ID in tqdm(IDs):
        try:
            # load compound
            X = nist.get_compound(ID)
            if not X:
                tqdm.write(f'Can not load the compound: {ID}')
                pass
            # load spectra
            getattr(X, method)()
            n_specs = len(getattr(X, specs))
            if not n_specs:
                tqdm.write(f'No spectra were downloaded for the compound: {ID}')
                time.sleep(crawl_delay)
                continue
            # save spectra
            getattr(X, save)(dir_out)
        except (KeyboardInterrupt, SystemError, SystemExit):
            raise
        except:
            tqdm.write(f'Error while processing compound # {ID}')
        time.sleep(min(30, crawl_delay*(n_specs + 1)))
    
    return



#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Downloads all available NIST Chemistry WebBook spectra of the given type')
    parser.add_argument('dir_out', help = 'directory to save downloaded spectra')
    parser.add_argument('spec_type', help = 'directory to save downloaded spectra')
    parser.add_argument('--crawl-delay', type = float, default = 5,
                        help = 'pause between HTTP requests, seconds')
    args = parser.parse_args()
    
    return args


def check_arguments(args: argparse.Namespace) -> None:
    '''Tries to create dir_data if it does not exist and raizes error if dir_data is a file
    
    Arguments:
        args (argparse.Namespace): input parameters
    
    '''
    # check save dir
    if not os.path.exists(args.dir_out):
        os.mkdir(args.dir_out) # FilexExistsError / FileNotFoundError
    if not os.path.isdir(args.dir_out):
        raise ValueError(f'Given dir_out argument is not a directory: {args.dir_out}')
    # spec type
    if args.spec_type not in ('IR', 'TZ', 'MS', 'UV'):
        raise ValueError(f'Spectra type argumant must be one of IR / TZ / MS / UV:: {args.spec_type}')
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
    print(f'\nDownloading {args.spec_type} spectra ...')
    download_spectra(args.dir_out, args.spec_type, args.crawl_delay)
    print()
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


