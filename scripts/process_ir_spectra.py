'''Process local raw IR spectra into a metadata CSV file.'''

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd
from jcamp import jcamp_readfile
from tqdm import tqdm

from common import (
    ensure_parent,
    load_webbook_index,
    require_data_terms_acknowledgement,
    split_id_argument,
)


DEFAULT_INPUT = 'local-data/raw/spectra/nist_IR.zip'
DEFAULT_OUTPUT = 'local-data/processed/nist_ir_info.csv'
MEMBER_RE = re.compile(
    r'^(?P<compound_id>[^_]+)_(?P<spec_type>[^_]+)_(?P<spec_idx>[^_]+)\.jdx$'
)
OUTPUT_COLUMNS = [
    'cID',
    'name',
    'inchi',
    'mp',
    'bp',
    'sID',
    'filename',
    'state',
    'state_original',
    'resolution',
    'spectrometer',
    'original_spectrum',
    'collection',
    'origin',
    'owner',
    'source_reference',
    'nist_source',
    'date',
]
DROP_COLUMNS = [
    'title',
    'jcamp-dx',
    'data type',
    'names',
    'molform',
    '$nist id',
    'xunits',
    'yunits',
    'xfactor',
    'yfactor',
    'deltax',
    'firstx',
    'lastx',
    'end',
    'firsty',
    'maxx',
    'minx',
    'maxy',
    'miny',
    'npoints',
    'xydata',
    'xlabel',
    'ylabel',
    'cas name',
    'cas registry no',
    'sampling procedure',
    'data processing',
    'path length',
    'instrument parameters',
    '$nist doc file',
    'instrument resolution',
    'ir source',
    'aperture',
    'beamsplitter',
    'detector',
    'scanner speed',
    'phase correction',
    'interferogram zerofill',
    'spectral interval after zerofilling',
    'spectral range',
    'apodization',
    'folding limits',
    'number of interferograms averaged per single channel spectrum',
    '$spectra version',
    '$uncertainty in y',
    'sample description',
    'pressure',
    'temperature',
    '$nist psd file',
    'external diffuse reflectance accessory',
    'detector (dia. det. port in sphere)',
    'sphere diameter',
    'acquisition mode',
    'coadded scans',
    'phase resolution',
    'zerofilling',
    'spectral resolution',
    'wavenumber accuracy',
    'apodization function',
    'low pass filter',
    'switch gain on',
]
RENAME_COLUMNS = {
    'class': 'collection',
    'source reference': 'source_reference',
    '$nist source': 'nist_source',
    '$nist image': 'original_spectrum',
    'spectrometer/data system': 'spectrometer',
    'state': 'state_original',
}
STATE_SUBSTITUTIONS = [
    ('vapor', 'gas'),
    ('(neat)', ''),
    ('neat', ''),
    ('thin', 'film'),
    ('saturated', 'solution'),
    ('oil', 'solid'),
    ('ssolid', 'solid'),
    ('visc.', 'paste'),
    ('salted', 'solution'),
    ('melted', 'liquid'),
    ('10%', 'solution'),
    ('melt', 'liquid'),
]


def _index_sort_key(value: str) -> tuple[int, str]:
    '''Return a stable sort key for spectrum indexes.'''
    try:
        return (int(value), value)
    except ValueError:
        return (10**9, value)


def parse_ir_member_name(member_name: str) -> tuple[str, str] | None:
    '''Parse an IR JDX archive member name.

    Args:
        member_name: ZIP member name.

    Returns:
        ``(compound_id, spectrum_index)`` for IR JDX files, otherwise ``None``.

    '''
    basename = Path(member_name).name
    match = MEMBER_RE.match(basename)
    if match is None:
        return None
    if match.group('spec_type').upper() != 'IR':
        return None
    return match.group('compound_id'), match.group('spec_idx')


def load_compound_metadata(
    index_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    '''Load compound names and InChI strings from the NistChemPy index.

    Args:
        index_path: Optional NistChemPy local index directory or CSV path.

    Returns:
        Mapping from WebBook compound ID to a metadata dictionary.

    Raises:
        ValueError: If the NistChemPy index lacks required columns.

    '''
    df = load_webbook_index(index_path)
    required = ['ID', 'name', 'inchi']
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f'NistChemPy index is missing required columns: {missing}')

    metadata = {}
    for _, row in df[required].iterrows():
        compound_id = str(row['ID'])
        metadata[compound_id] = {
            'name': '' if pd.isna(row['name']) else row['name'],
            'inchi': '' if pd.isna(row['inchi']) else row['inchi'],
        }
    return metadata


def collect_ir_members(
    zipf: zipfile.ZipFile,
    ids: list[str] | None = None,
    limit: int | None = None,
) -> list[tuple[str, str, str]]:
    '''Collect IR JDX archive members to process.

    Args:
        zipf: Open ZIP archive.
        ids: Optional ordered compound-ID filter.
        limit: Optional maximum number of selected members.

    Returns:
        List of ``(compound_id, spectrum_index, member_name)`` tuples.

    '''
    id_order = None if ids is None else {compound_id: idx for idx, compound_id in enumerate(ids)}
    members = []

    for info in zipf.infolist():
        if info.is_dir():
            continue
        parsed = parse_ir_member_name(info.filename)
        if parsed is None:
            continue
        compound_id, spectrum_index = parsed
        if id_order is not None and compound_id not in id_order:
            continue
        members.append((compound_id, spectrum_index, info.filename))

    if id_order is None:
        members = sorted(members, key=lambda item: (item[0], _index_sort_key(item[1])))
    else:
        members = sorted(
            members,
            key=lambda item: (id_order[item[0]], _index_sort_key(item[1])),
        )

    if limit is not None:
        members = members[:limit]

    return members


def read_jdx_metadata(zipf: zipfile.ZipFile, member_name: str) -> dict[str, Any]:
    '''Read one JDX archive member with jcamp.

    Args:
        zipf: Open ZIP archive.
        member_name: Member name inside the archive.

    Returns:
        JCAMP metadata dictionary without the large ``x`` and ``y`` arrays.

    Raises:
        ValueError: If the JCAMP reader does not return a metadata dictionary.

    '''
    temp_path = None
    try:
        with NamedTemporaryFile(mode='wb', suffix='.jdx', delete=False) as temp_file:
            temp_file.write(zipf.read(member_name))
            temp_path = Path(temp_file.name)

        data = jcamp_readfile(str(temp_path))
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    if not isinstance(data, dict):
        raise ValueError('JCAMP reader did not return a metadata dictionary')

    data.pop('x', None)
    data.pop('y', None)
    return data


def normalize_state(value: str) -> str:
    '''Normalize a raw IR state string to a compact coarse state label.

    Args:
        value: Raw state string from the JDX metadata.

    Returns:
        Coarse state label such as ``gas``, ``liquid``, ``solid``, or an empty
        string if no state could be inferred.

    '''
    text = re.sub(r'([a-zA-Z])\(', r'\1 \(', str(value)).lower()
    state = text.split()[0] if text else ''
    state = state.strip(';,')
    for source, replacement in STATE_SUBSTITUTIONS:
        if state == source:
            return replacement
    return state


def process_df(df: pd.DataFrame) -> pd.DataFrame:
    '''Process raw IR JDX metadata rows.

    Args:
        df: Raw DataFrame compiled from IR spectra.

    Returns:
        Processed metadata table with the historical output columns where
        possible.

    '''
    df = df.copy()
    df = df.drop(columns=DROP_COLUMNS, errors='ignore')
    df = df.rename(columns=RENAME_COLUMNS)

    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = ''

    df['state_original'] = df['state_original'].fillna('').astype(str)
    df['owner'] = df['owner'].fillna('').astype(str).str.replace('\n', ' ', regex=False)
    df['filename'] = df['cID'].astype(str) + '_IR_' + df['sID'].astype(str) + '.jdx'
    df['state'] = df['state_original'].apply(normalize_state)

    return df[OUTPUT_COLUMNS]


def process_ir_spectra(
    path_zip: str | Path,
    path_out: str | Path,
    ids: list[str] | None = None,
    limit: int | None = None,
    index_path: str | Path | None = None,
) -> None:
    '''Extract IR metadata from a local raw JDX ZIP archive.

    Args:
        path_zip: ZIP archive containing raw IR JDX files.
        path_out: Output CSV path.
        ids: Optional ordered compound-ID filter.
        limit: Optional maximum number of selected members to process.
        index_path: Optional NistChemPy local index directory or CSV path.

    Raises:
        ValueError: If no IR JDX members are found.
        RuntimeError: If any selected JDX member cannot be processed.

    '''
    metadata = load_compound_metadata(index_path)
    rows = []

    with zipfile.ZipFile(path_zip, 'r') as zipf:
        members = collect_ir_members(zipf, ids=ids, limit=limit)
        if not members:
            raise ValueError('No IR JDX members were found in the input archive')

        for compound_id, spectrum_index, member_name in tqdm(members, total=len(members)):
            try:
                jdx_metadata = read_jdx_metadata(zipf, member_name)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                raise RuntimeError(f'Cannot process IR archive member: {member_name}') from exc

            compound_metadata = metadata.get(compound_id, {'name': '', 'inchi': ''})
            row = {
                'cID': compound_id,
                'name': compound_metadata['name'],
                'inchi': compound_metadata['inchi'],
                'sID': spectrum_index,
                **jdx_metadata,
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    df = process_df(df)
    df = df.sort_values(['cID', 'sID'], key=lambda col: col.astype(str))
    ensure_parent(path_out)
    df.to_csv(path_out, index=False)


def positive_int(value: str) -> int:
    '''Parse a positive integer CLI value.'''
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError('value must be a positive integer')
    return parsed


def get_arguments() -> argparse.Namespace:
    '''Parse CLI arguments.

    Returns:
        Parsed CLI arguments.

    '''
    parser = argparse.ArgumentParser(
        description='Extract metadata from a local raw IR spectra ZIP archive.',
    )
    parser.add_argument(
        'path_zip',
        nargs='?',
        default=DEFAULT_INPUT,
        help=f'input ZIP archive containing raw IR spectra, default: {DEFAULT_INPUT}',
    )
    parser.add_argument(
        'path_out',
        nargs='?',
        default=DEFAULT_OUTPUT,
        help=f'output CSV file, default: {DEFAULT_OUTPUT}',
    )
    parser.add_argument(
        '--ids',
        help='comma-separated compound IDs to process in the given order',
    )
    parser.add_argument(
        '--limit',
        type=positive_int,
        help='maximum number of selected IR JDX members to process',
    )
    parser.add_argument(
        '--accept-data-terms',
        action='store_true',
        help='acknowledge that generated files are local data artifacts',
    )
    return parser.parse_args()


def check_arguments(args: argparse.Namespace) -> None:
    '''Check CLI path arguments.

    Args:
        args: Parsed CLI arguments.

    Raises:
        ValueError: If the input archive does not exist.

    '''
    if not Path(args.path_zip).exists():
        raise ValueError(f'Input ZIP archive does not exist: {args.path_zip}')


def main() -> None:
    '''Process local IR metadata and save it to CSV.'''
    args = get_arguments()
    require_data_terms_acknowledgement(args.accept_data_terms)
    check_arguments(args)

    print('\nProcessing IR spectra ...')
    process_ir_spectra(
        path_zip=args.path_zip,
        path_out=args.path_out,
        ids=split_id_argument(args.ids),
        limit=args.limit,
    )
    print(f'Wrote IR metadata table to {args.path_out}\n')


if __name__ == '__main__':
    main()
