'''Process local raw MS spectra into JSONL or JSON peak-list files.'''

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from tqdm import tqdm

from common import (
    ensure_parent,
    load_webbook_index,
    require_data_terms_acknowledgement,
    split_id_argument,
)


DEFAULT_INPUT = 'local-data/raw/spectra/nist_MS.zip'
DEFAULT_OUTPUT = 'local-data/processed/nist_ms.jsonl'
MEMBER_RE = re.compile(
    r'^(?P<compound_id>[^_]+)_(?P<spec_type>[^_]+)_(?P<spec_idx>[^_]+)\.jdx$'
)
PEAK_RE = re.compile(r'(?<![\w.])(\d+)\s*,\s*(\d+)(?![\w.])')


def _index_sort_key(value: str) -> tuple[int, str]:
    '''Return a stable sort key for spectrum indexes.'''
    try:
        return (int(value), value)
    except ValueError:
        return (10**9, value)


def jdx_text_to_spectra(text: str) -> tuple[list[int], list[int]]:
    '''Extract an MS peak list from a JDX text block.

    Args:
        text: Raw JDX file text.

    Returns:
        Two lists: m/z values and relative intensities, sorted by m/z.

    Raises:
        ValueError: If no integer ``m/z,intensity`` pairs are found.

    '''
    pairs = [(int(mz), int(intensity)) for mz, intensity in PEAK_RE.findall(text)]
    if not pairs:
        raise ValueError('no integer m/z,intensity peak pairs found')

    pairs = sorted(pairs)
    mz_values, intensities = zip(*pairs)
    return list(mz_values), list(intensities)


def infer_output_format(
    path_out: str | Path,
    output_format: str | None = None,
) -> Literal['jsonl', 'json']:
    '''Infer or validate the processed MS output format.

    Args:
        path_out: Output path.
        output_format: Optional explicit output format.

    Returns:
        Either ``'jsonl'`` or ``'json'``.

    Raises:
        ValueError: If the explicit output format is unsupported.

    '''
    if output_format is not None:
        if output_format not in {'jsonl', 'json'}:
            raise ValueError(f'Unsupported output format: {output_format}')
        return output_format

    suffix = Path(path_out).suffix.lower()
    if suffix == '.json':
        return 'json'
    return 'jsonl'


def write_ms_records(
    records: list[dict[str, Any]],
    path_out: str | Path,
    output_format: Literal['jsonl', 'json'],
) -> None:
    '''Write processed MS records to JSONL or JSON.

    Args:
        records: Processed spectrum records.
        path_out: Output path.
        output_format: Output format.

    '''
    ensure_parent(path_out)
    with Path(path_out).open('w', encoding='utf-8') as out_file:
        if output_format == 'jsonl':
            for record in records:
                line = json.dumps(
                    record,
                    ensure_ascii=False,
                    separators=(',', ':'),
                )
                out_file.write(line + '\n')
        else:
            json.dump(records, out_file, ensure_ascii=False, indent=0)


def parse_ms_member_name(member_name: str) -> tuple[str, str] | None:
    '''Parse an MS JDX archive member name.

    Args:
        member_name: ZIP member name.

    Returns:
        ``(compound_id, spectrum_index)`` for MS JDX files, otherwise ``None``.

    '''
    basename = os.path.basename(member_name)
    match = MEMBER_RE.match(basename)
    if match is None:
        return None
    if match.group('spec_type').upper() != 'MS':
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
            'name': '' if row['name'] != row['name'] else row['name'],
            'inchi': '' if row['inchi'] != row['inchi'] else row['inchi'],
        }
    return metadata


def collect_ms_members(
    zipf: zipfile.ZipFile,
    ids: list[str] | None = None,
    spectrum_policy: str = 'first',
    limit: int | None = None,
) -> list[tuple[str, str, str]]:
    '''Collect archive members to process.

    Args:
        zipf: Open ZIP archive.
        ids: Optional ordered compound-ID filter.
        spectrum_policy: ``first`` to process one spectrum per compound, or
            ``all`` to process every MS JDX member.
        limit: Optional maximum number of selected members or compounds.

    Returns:
        Tuples of ``(compound_id, spectrum_index, member_name)``.

    '''
    id_order = None
    if ids is not None:
        id_order = {compound_id: idx for idx, compound_id in enumerate(ids)}
    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    for info in zipf.infolist():
        if info.is_dir():
            continue
        parsed = parse_ms_member_name(info.filename)
        if parsed is None:
            continue
        compound_id, spec_idx = parsed
        if id_order is not None and compound_id not in id_order:
            continue
        grouped[compound_id].append((compound_id, spec_idx, info.filename))

    if id_order is not None:
        compound_ids = sorted(grouped, key=lambda item: id_order[item])
    else:
        compound_ids = sorted(grouped)

    selected = []
    for compound_id in compound_ids:
        members = sorted(
            grouped[compound_id],
            key=lambda item: _index_sort_key(item[1]),
        )
        if spectrum_policy == 'first':
            selected.append(members[0])
        else:
            selected.extend(members)

        if limit is not None and len(selected) >= limit:
            selected = selected[:limit]
            break

    return selected


def process_ms_spectra(
    path_zip: str | Path,
    path_out: str | Path,
    spectrum_policy: str = 'first',
    ids: list[str] | None = None,
    limit: int | None = None,
    output_format: str | None = None,
    index_path: str | Path | None = None,
) -> None:
    '''Process a local raw MS archive and write peak-list records.

    Args:
        path_zip: ZIP archive containing raw MS JDX files.
        path_out: Output JSONL or JSON path.
        spectrum_policy: ``first`` for one spectrum per compound, or ``all`` for
            all MS spectra in the archive.
        ids: Optional ordered compound-ID filter.
        limit: Optional maximum number of selected members to process.
        output_format: Optional explicit output format. If omitted, ``.json``
            outputs a JSON array and all other suffixes use JSON Lines.
        index_path: Optional NistChemPy local index directory or CSV path.

    Raises:
        ValueError: If ``spectrum_policy`` or ``output_format`` is unsupported.

    '''
    if spectrum_policy not in {'first', 'all'}:
        raise ValueError(f'Unsupported spectrum policy: {spectrum_policy}')

    resolved_output_format = infer_output_format(path_out, output_format)
    metadata = load_compound_metadata(index_path)
    data = []

    with zipfile.ZipFile(path_zip, 'r') as zipf:
        members = collect_ms_members(
            zipf,
            ids=ids,
            spectrum_policy=spectrum_policy,
            limit=limit,
        )

        for compound_id, spec_idx, member_name in tqdm(members, total=len(members)):
            try:
                text = zipf.read(member_name).decode('utf-8', errors='replace')
                mz_values, intensities = jdx_text_to_spectra(text)
                compound_metadata = metadata.get(compound_id, {'name': '', 'inchi': ''})
                if compound_id not in metadata:
                    tqdm.write(
                        f'Metadata not found for {compound_id}; using empty fields'
                    )

                item = {
                    'ID': compound_id,
                    'name': compound_metadata['name'],
                    'inchi': compound_metadata['inchi'],
                    'mz': mz_values,
                    'intensities': intensities,
                }
                if spectrum_policy == 'all':
                    item['spectrum_index'] = spec_idx
                    item['source_member'] = member_name

                data.append(item)
            except Exception as exc:
                raise RuntimeError(
                    f'Error while processing {member_name}: {exc}'
                ) from exc

    write_ms_records(data, path_out, resolved_output_format)


def get_arguments() -> argparse.Namespace:
    '''Parse command-line arguments.

    Returns:
        Parsed CLI arguments.

    '''
    parser = argparse.ArgumentParser(
        description='Process local raw MS JDX archive into JSONL or JSON peak lists.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'path_zip',
        nargs='?',
        default=DEFAULT_INPUT,
        help='input ZIP archive containing raw MS JDX files',
    )
    parser.add_argument(
        'path_out',
        nargs='?',
        default=DEFAULT_OUTPUT,
        help='output JSONL or JSON file',
    )
    parser.add_argument(
        '--format',
        dest='output_format',
        choices=['jsonl', 'json'],
        help='output format; inferred from output suffix when omitted',
    )
    parser.add_argument(
        '--spectrum-policy',
        choices=['first', 'all'],
        default='first',
        help='process the first MS spectrum per compound or all MS spectra',
    )
    parser.add_argument(
        '--ids',
        help='comma-separated compound IDs to process instead of all available IDs',
    )
    parser.add_argument(
        '--index-path',
        help='NistChemPy local index directory or CSV path',
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='maximum number of selected members to process',
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
    if not Path(args.path_zip).exists():
        raise ValueError(f'Input ZIP archive does not exist: {args.path_zip}')
    if args.limit is not None and args.limit <= 0:
        raise ValueError(f'--limit must be positive: {args.limit}')


def main() -> None:
    '''Process local raw MS spectra into JSONL or JSON peak lists.'''
    args = get_arguments()
    check_arguments(args)
    require_data_terms_acknowledgement(args.accept_data_terms)

    ids = split_id_argument(args.ids)
    output_format = infer_output_format(args.path_out, args.output_format)

    print('\nProcessing MS spectra ...')
    print(f'Input archive: {args.path_zip}')
    print(f'Output {output_format.upper()}: {args.path_out}')
    process_ms_spectra(
        args.path_zip,
        args.path_out,
        spectrum_policy=args.spectrum_policy,
        ids=ids,
        limit=args.limit,
        output_format=args.output_format,
        index_path=args.index_path,
    )
    print()


if __name__ == '__main__':
    main()
