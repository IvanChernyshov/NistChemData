'''Combine a local raw GC parts archive into a single CSV table.'''

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from common import (
    ensure_parent,
    gc_archive_members_by_compound,
    load_webbook_index,
    parse_legacy_gc_member_name,
    require_data_terms_acknowledgement,
    split_id_argument,
)


DEFAULT_INPUT = 'local-data/raw/nist_gc_parts.zip'
DEFAULT_OUTPUT = 'local-data/processed/nist_gc.csv'
DEFAULT_ZIP_OUTPUT = 'local-data/processed/nist_gc.zip'
METADATA_COLUMNS = [
    'Compound ID',
    'Compound name',
    'InChI',
    'Retention index type',
    'Column polarity',
    'Temperature regime',
]


def _id_sort_key(compound_id: str) -> tuple[str, int, str]:
    '''Return a stable sort key for WebBook compound IDs.'''
    prefix = ''.join(ch for ch in compound_id if not ch.isdigit())
    digits = ''.join(ch for ch in compound_id if ch.isdigit())
    number = int(digits) if digits else -1
    return prefix, number, compound_id


def load_compound_metadata(
    index_path: str | Path | None = None,
) -> dict[str, dict[str, object]]:
    '''Load compound name/InChI metadata from the NistChemPy index.

    Args:
        index_path: Optional NistChemPy local index directory or CSV path.

    Returns:
        Mapping from compound ID to metadata dictionaries.

    '''
    df = load_webbook_index(index_path)
    cols = ['ID', 'name', 'inchi']
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise ValueError(f'Missing columns in NistChemPy index: {missing}')

    meta = df[cols].copy()
    meta = meta.where(pd.notna(meta), '')
    meta = meta.set_index('ID')
    return meta.to_dict('index')


def collect_gc_members(
    path_zip: str | Path,
    ids: list[str] | None = None,
    limit: int | None = None,
) -> list[tuple[str, str]]:
    '''Collect GC archive members to process.

    Args:
        path_zip: Raw GC parts ZIP archive path.
        ids: Optional ordered compound-ID filter.
        limit: Optional maximum number of selected members.

    Returns:
        List of ``(compound_id, archive_member)`` tuples.

    '''
    grouped = gc_archive_members_by_compound(path_zip, require_nonempty=True)
    id_order = None
    if ids is not None:
        id_order = {compound_id: idx for idx, compound_id in enumerate(ids)}

    records = []
    for compound_id, members in grouped.items():
        if id_order is not None and compound_id not in id_order:
            continue
        for member in sorted(members.values()):
            records.append((compound_id, member))

    if id_order is None:
        records = sorted(records, key=lambda item: (_id_sort_key(item[0]), item[1]))
    else:
        records = sorted(records, key=lambda item: (id_order[item[0]], item[1]))

    if limit is not None:
        records = records[:limit]

    return records


def read_gc_part(zipf: zipfile.ZipFile, member_name: str) -> pd.DataFrame:
    '''Read one GC CSV part from a ZIP archive.

    Args:
        zipf: Open ZIP archive.
        member_name: Archive member name.

    Returns:
        DataFrame loaded from the CSV part.

    Raises:
        RuntimeError: If the CSV part cannot be read.

    '''
    try:
        with zipf.open(member_name) as in_file:
            return pd.read_csv(in_file)
    except Exception as exc:
        raise RuntimeError(
            f'failed to read GC CSV member {member_name}: {exc}'
        ) from exc


def add_metadata_columns(
    df: pd.DataFrame,
    member_name: str,
    compound_metadata: dict[str, dict[str, object]],
) -> pd.DataFrame:
    '''Add compound and GC-table metadata columns to a GC part table.

    Args:
        df: Raw GC part table.
        member_name: Archive member name, used to parse table metadata.
        compound_metadata: Mapping from compound ID to name/InChI metadata.

    Returns:
        DataFrame with metadata columns prepended.

    Raises:
        ValueError: If the member name does not follow the expected convention.

    '''
    info = parse_legacy_gc_member_name(member_name)
    compound_id = info['compound_id']
    meta = compound_metadata.get(compound_id, {})

    metadata = {
        'Compound ID': compound_id,
        'Compound name': meta.get('name', ''),
        'InChI': meta.get('inchi', ''),
        'Retention index type': info['ri_type'],
        'Column polarity': info['column_type'],
        'Temperature regime': info['temp_regime'],
    }

    data = df.drop(columns=[col for col in METADATA_COLUMNS if col in df.columns])
    meta_frame = pd.DataFrame([metadata] * len(data))
    return pd.concat([meta_frame, data.reset_index(drop=True)], axis=1)


def process_gas_chromatography(
    path_zip: str | Path,
    path_csv: str | Path,
    path_zip_csv: str | Path | None = None,
    ids: list[str] | None = None,
    limit: int | None = None,
    index_path: str | Path | None = None,
) -> None:
    '''Combine local raw GC CSV parts into one table.

    Args:
        path_zip: Raw GC parts ZIP archive path.
        path_csv: Output combined CSV path.
        path_zip_csv: Optional ZIP archive path for the generated CSV file.
        ids: Optional ordered compound-ID filter.
        limit: Optional maximum number of raw parts to process.
        index_path: Optional NistChemPy local index directory or CSV path.

    '''
    path_zip = Path(path_zip)
    path_csv = Path(path_csv)
    if not path_zip.exists():
        raise FileNotFoundError(f'Input archive not found: {path_zip}')
    ensure_parent(path_csv)

    members = collect_gc_members(path_zip, ids=ids, limit=limit)
    if not members:
        raise ValueError(f'No non-empty GC CSV members found in archive: {path_zip}')

    compound_metadata = load_compound_metadata(index_path)
    tables = []

    with zipfile.ZipFile(path_zip, 'r') as zipf:
        for _, member_name in tqdm(members, total=len(members)):
            df = read_gc_part(zipf, member_name)
            tables.append(add_metadata_columns(df, member_name, compound_metadata))

    combined = pd.concat(tables, ignore_index=True)
    sort_cols = [
        'Compound ID',
        'Column polarity',
        'Active phase',
        'Retention index type',
        'Temperature regime',
    ]
    sort_cols = [col for col in sort_cols if col in combined.columns]
    if sort_cols:
        combined = combined.sort_values(sort_cols)

    combined.to_csv(path_csv, index=False)

    if path_zip_csv is not None:
        path_zip_csv = Path(path_zip_csv)
        ensure_parent(path_zip_csv)
        with zipfile.ZipFile(
            path_zip_csv, 'w', compression=zipfile.ZIP_DEFLATED
        ) as zipf:
            zipf.write(path_csv, arcname=path_csv.name)


def get_arguments() -> argparse.Namespace:
    '''Parse command-line arguments.

    Returns:
        Parsed CLI arguments.

    '''
    parser = argparse.ArgumentParser(
        description='Combine local raw GC table parts into one CSV table.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'input_zip',
        nargs='?',
        default=DEFAULT_INPUT,
        help='input raw GC parts ZIP archive path',
    )
    parser.add_argument(
        'output_csv',
        nargs='?',
        default=DEFAULT_OUTPUT,
        help='output combined CSV path',
    )
    parser.add_argument(
        '--zip-output',
        nargs='?',
        const=DEFAULT_ZIP_OUTPUT,
        help='optional ZIP path for the generated combined CSV',
    )
    parser.add_argument(
        '--ids',
        help='comma-separated compound IDs to process instead of all archive members',
    )
    parser.add_argument(
        '--index-path',
        help='NistChemPy local index directory or CSV path',
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='maximum number of raw GC parts to process',
    )
    parser.add_argument(
        '--accept-data-terms',
        action='store_true',
        help='acknowledge that generated files are local artifacts',
    )

    return parser.parse_args()


def check_arguments(args: argparse.Namespace) -> None:
    '''Validate command-line arguments.

    Args:
        args: Parsed CLI arguments.

    Raises:
        ValueError: If an argument is invalid.

    '''
    if args.limit is not None and args.limit <= 0:
        raise ValueError(f'--limit must be positive: {args.limit}')


def main() -> None:
    '''Combine local raw GC table parts into one CSV table.'''
    args = get_arguments()
    check_arguments(args)
    require_data_terms_acknowledgement(args.accept_data_terms)

    ids = split_id_argument(args.ids)

    print('\nCombining GC table parts ...')
    print(f'Input archive: {args.input_zip}')
    print(f'Output CSV: {args.output_csv}')
    if args.zip_output:
        print(f'Output ZIP: {args.zip_output}')

    process_gas_chromatography(
        args.input_zip,
        args.output_csv,
        path_zip_csv=args.zip_output,
        ids=ids,
        limit=args.limit,
        index_path=args.index_path,
    )
    print()


if __name__ == '__main__':
    main()
