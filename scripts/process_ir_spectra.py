'''Extracts meta-info from JDX files and saves them in tabular format'''

#%% Imports

import re, os, zipfile, tempfile, argparse

import pandas as pd

from jcamp import jcamp_readfile

from tqdm import tqdm


#%% Functions

def process_df(df: pd.core.frame.DataFrame) -> pd.core.frame.DataFrame:
    '''Processes raw dataframe compiled from IR spectra'''
    # drop unneeded
    drop = [
        'title', 'jcamp-dx', 'data type', 'names', 'molform', '$nist id',
        'xunits', 'yunits', 'xfactor', 'yfactor', 'deltax', 'firstx', 'lastx', 'end',
        'firsty', 'maxx', 'minx', 'maxy', 'miny', 'npoints', 'xydata', 'xlabel', 'ylabel',
        'filename', 'cas name', 'cas registry no',
        'sampling procedure', 'data processing', 'path length', 'instrument parameters',
        '$nist doc file', 'instrument resolution', 'ir source',
        'aperture', 'beamsplitter', 'detector', 'scanner speed',
        'phase correction', 'interferogram zerofill', 'spectral interval after zerofilling',
        'spectral range', 'apodization', 'folding limits',
        'number of interferograms averaged per single channel spectrum',
        '$spectra version', '$uncertainty in y', 'sample description', 'pressure', 'temperature',
        '$nist psd file', 'external diffuse reflectance accessory',
        'detector (dia. det. port in sphere)', 'sphere diameter',
        'acquisition mode', 'coadded scans', 'phase resolution', 'zerofilling',
        'spectral resolution', 'wavenumber accuracy', 'apodization function',
        'low pass filter', 'switch gain on'
    ]
    df = df.drop(columns=drop)
    
    # rename
    rename = {
        'class': 'collection',
        'source reference': 'source_reference',
        '$nist source': 'nist_source',
        '$nist image': 'original_spectrum',
        'spectrometer/data system': 'spectrometer',
        'state': 'state_original'
    }
    df = df.rename(columns=rename)
    
    # process
    df['state'] = ''
    df.loc[df['state_original'].isna(), 'state_original'] = ''
    df.owner = df.owner.str.replace('\n', ' ')
    
    # filename
    df['filename'] = df['cID'] + '_IR_' + df['sID'].astype('str') + '.jdx'
    
    # reorder columns
    cols = ['cID', 'name', 'inchi', 'mp', 'bp', 'sID', 'filename', 'state', 'state_original',
            'resolution', 'spectrometer', 'original_spectrum',
            'collection', 'origin', 'owner', 'source_reference', 'nist_source', 'date']
    df = df[cols]
    
    # state
    x = df['state_original'].apply(lambda x: re.sub(r'([a-zA-Z])\(', r'\1 \(', x)).astype(str).str.lower()
    state = x.apply(lambda x: x.split()[0] if x else '')
    state = state.str.strip(';,')
    subs = [
        ('vapor', 'gas'), ('(neat)', ''), ('neat', ''), ('thin', 'film'),
        ('saturated', 'solution'), ('oil', 'solid'), ('ssolid', 'solid'),
        ('visc.', 'paste'), ('salted', 'solution'), ('melted', 'liquid'),
        ('10%', 'solution'), ('melt', 'liquid')
    ]
    for sub, rep in subs:
        state.loc[state == sub] = rep
    df['state'] = state
    
    return df


def process_ir_spectra(path_zip: str, path_comp: str, path_out: str) -> None:
    '''Extracts meta-info on IR spectra and saves it to csv-file
    
    Arguments:
        path_zip (str): zip-file containing raw IR spectra
        path_comp (str): path to compounds.csv file
        path_out (str): output csv file
    
    '''
    # prepare names and inchis
    main = pd.read_csv(path_comp, low_memory=False)
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
            cID, _, sID = os.path.basename(f.filename).replace('.jdx', '').split('_')
            try:
                # read file
                with tempfile.TemporaryFile(mode='wb', delete=False) as jdx:
                    text = zipf.read(f)
                    jdx.write(text)
                    jdx.close()
                    X = jcamp_readfile(jdx.name)
                    os.remove(jdx.name)
                # form row
                for key in ('x', 'y'):
                    X.pop(key)
                X = {'cID': cID, 'name': main.loc[cID, 'name'],
                     'inchi': main.loc[cID, 'inchi'], 'sID': sID, **X}
                data.append(X)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                tqdm.write(f'Cannot process {cID} compound, spectrum #{sID}')
                continue
    
    # save csv
    df = pd.DataFrame(data)
    df = df.sort_values(['cID', 'sID'])
    df = process_df(df)
    df.to_csv(path_out, index=None)
    
    return


#%% Main functions

def get_arguments() -> argparse.Namespace:
    '''CLI wrapper
    
    Returns:
        argparse.Namespace: CLI arguments
    
    '''
    parser = argparse.ArgumentParser(description = 'Extracts annotation from raw IR spectra')
    parser.add_argument('path_zip', help = 'zip-file containing raw IR spectra')
    parser.add_argument('path_comp', help = 'compounds.csv')
    parser.add_argument('path_out', help = 'output CSV-file')
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
    if dir_out and not os.path.isdir(dir_out):
        raise ValueError(f'Output directory does not exist: {args.path_out}')
    
    return


def main() -> None:
    '''Processes MS spectra and saves them to json file'''
    
    # prepare arguments
    args = get_arguments()
    check_arguments(args)
    
    # process spectra
    print('\nProcessing IR spectra ...')
    process_ir_spectra(args.path_zip, args.path_comp, args.path_out)
    print()
    
    return



#%% Main

if __name__ == '__main__':
    
    main()


