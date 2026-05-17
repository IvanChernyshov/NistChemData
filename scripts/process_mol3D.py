'''Assemble a local raw 3D MOL archive into an SDF file.'''

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from tqdm import tqdm

from common import (
    ensure_parent,
    mol_archive_members_by_compound,
    require_data_terms_acknowledgement,
    split_id_argument,
)


DEFAULT_INPUT = 'local-data/raw/nist_mol3D_raw.zip'
DEFAULT_OUTPUT = 'local-data/processed/nist_mol3D.sdf'


def _id_sort_key(compound_id: str) -> tuple[str, int, str]:
    '''Return a stable sort key for WebBook compound IDs.'''
    prefix = ''.join(ch for ch in compound_id if not ch.isdigit())
    digits = ''.join(ch for ch in compound_id if ch.isdigit())
    number = int(digits) if digits else -1
    return prefix, number, compound_id


def collect_mol_members(
    path_zip: str | Path,
    ids: list[str] | None = None,
    limit: int | None = None,
) -> list[tuple[str, str]]:
    '''Collect MOL archive members to process.

    Args:
        path_zip: Raw MOL ZIP archive path.
        ids: Optional ordered compound-ID filter.
        limit: Optional maximum number of selected records.

    Returns:
        List of ``(compound_id, archive_member)`` tuples.

    '''
    grouped = mol_archive_members_by_compound(path_zip, require_nonempty=True)
    id_order = None
    if ids is not None:
        id_order = {compound_id: idx for idx, compound_id in enumerate(ids)}

    records = []
    for compound_id, members in grouped.items():
        if id_order is not None and compound_id not in id_order:
            continue
        canonical = f'{compound_id}.mol'
        member = members.get(canonical)
        if member is None:
            member = sorted(members.values())[0]
        records.append((compound_id, member))

    if id_order is None:
        records = sorted(records, key=lambda item: _id_sort_key(item[0]))
    else:
        records = sorted(records, key=lambda item: id_order[item[0]])

    if limit is not None:
        records = records[:limit]

    return records


def normalize_sdf_record(text: str, member_name: str) -> str:
    '''Normalize one downloaded MOL/SDF record for SDF concatenation.

    Args:
        text: Downloaded MOL/SDF text.
        member_name: Archive member name, used for error messages.

    Returns:
        SDF record ending with exactly one ``$$$$`` separator and a newline.

    Raises:
        ValueError: If the record is empty.

    '''
    record = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not record:
        raise ValueError(f'empty MOL record: {member_name}')
    if not record.rstrip().endswith('$$$$'):
        record = record.rstrip() + '\n$$$$'
    return record.rstrip() + '\n'


def _mol_block_for_validation(record: str) -> str:
    '''Extract the MOL block portion of an SDF record for RDKit validation.'''
    lines = []
    for line in record.splitlines():
        lines.append(line)
        if line.strip() == 'M  END':
            break
    return '\n'.join(lines) + '\n'


def validate_record(record: str, member_name: str) -> None:
    '''Validate one MOL record with RDKit.

    Args:
        record: Normalized SDF record.
        member_name: Archive member name, used for error messages.

    Raises:
        RuntimeError: If RDKit is unavailable.
        ValueError: If RDKit cannot parse the MOL block.

    '''
    try:
        from rdkit import Chem
        from rdkit import RDLogger
    except ImportError as exc:
        raise RuntimeError('RDKit is required for --validate') from exc

    RDLogger.DisableLog('rdApp.*')
    mol = Chem.MolFromMolBlock(
        _mol_block_for_validation(record),
        removeHs=False,
        sanitize=False,
        strictParsing=False,
    )
    if mol is None:
        raise ValueError(f'RDKit could not parse MOL record: {member_name}')


def process_mol3d(
    path_zip: str | Path,
    path_sdf: str | Path,
    path_zip_sdf: str | Path | None = None,
    ids: list[str] | None = None,
    limit: int | None = None,
    validate: bool = False,
) -> None:
    '''Assemble a local raw MOL archive into an SDF file.

    Args:
        path_zip: Raw MOL ZIP archive path.
        path_sdf: Output SDF file path.
        path_zip_sdf: Optional ZIP archive path for the generated SDF file.
        ids: Optional ordered compound-ID filter.
        limit: Optional maximum number of selected records.
        validate: Whether to validate MOL blocks with RDKit before writing.

    '''
    path_zip = Path(path_zip)
    path_sdf = Path(path_sdf)
    if not path_zip.exists():
        raise FileNotFoundError(f'Input archive not found: {path_zip}')
    ensure_parent(path_sdf)

    members = collect_mol_members(path_zip, ids=ids, limit=limit)
    if not members:
        raise ValueError(f'No non-empty MOL members found in archive: {path_zip}')

    records = []

    with zipfile.ZipFile(path_zip, 'r') as zipf:
        for _, member_name in tqdm(members, total=len(members)):
            text = zipf.read(member_name).decode('utf-8', errors='replace')
            record = normalize_sdf_record(text, member_name)
            if validate:
                validate_record(record, member_name)
            records.append(record)

    path_sdf.write_text(''.join(records), encoding='utf-8')

    if path_zip_sdf is not None:
        path_zip_sdf = Path(path_zip_sdf)
        ensure_parent(path_zip_sdf)
        with zipfile.ZipFile(
            path_zip_sdf, 'w', compression=zipfile.ZIP_DEFLATED
        ) as zipf:
            zipf.write(path_sdf, arcname=path_sdf.name)


def get_arguments() -> argparse.Namespace:
    '''Parse command-line arguments.

    Returns:
        Parsed CLI arguments.

    '''
    parser = argparse.ArgumentParser(
        description='Assemble a local raw 3D MOL archive into an SDF file.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'input_zip',
        nargs='?',
        default=DEFAULT_INPUT,
        help='input raw MOL ZIP archive path',
    )
    parser.add_argument(
        'output_sdf',
        nargs='?',
        default=DEFAULT_OUTPUT,
        help='output SDF file path',
    )
    parser.add_argument(
        '--zip-output',
        help='optional ZIP path for the generated SDF file',
    )
    parser.add_argument(
        '--ids',
        help='comma-separated compound IDs to process instead of all archive members',
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='maximum number of MOL records to process',
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='validate MOL blocks with RDKit before writing the SDF',
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
    '''Assemble local SDF from a raw MOL archive.'''
    args = get_arguments()
    check_arguments(args)
    require_data_terms_acknowledgement(args.accept_data_terms)

    ids = split_id_argument(args.ids)

    print('\nAssembling local 3D SDF ...')
    print(f'Input archive: {args.input_zip}')
    print(f'Output SDF: {args.output_sdf}')
    if args.zip_output is not None:
        print(f'Output ZIP: {args.zip_output}')

    process_mol3d(
        args.input_zip,
        args.output_sdf,
        path_zip_sdf=args.zip_output,
        ids=ids,
        limit=args.limit,
        validate=args.validate,
    )
    print()


if __name__ == '__main__':
    main()
