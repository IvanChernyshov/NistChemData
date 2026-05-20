'''Download local NIST Chemistry WebBook 3D MOL archives.'''

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from tqdm import tqdm

from common import (
    MANIFEST_COLUMNS,
    RIGHTS_STATUS,
    SOURCE_DATABASE,
    append_manifest_row,
    completed_ids_for_download,
    ensure_parent,
    filter_index_rows,
    format_archive_members,
    load_webbook_index,
    make_request_config,
    mol_archive_members_by_compound,
    request_nist,
    require_data_terms_acknowledgement,
    split_id_argument,
    utc_now,
)


DEFAULT_OUTPUT = 'local-data/raw/nist_mol3D_raw.zip'
DEFAULT_MANIFEST = 'local-data/manifests/nist_mol3D_manifest.csv'
DATA_TYPE = 'mol3D'
SOURCE_COLUMN = 'mol3D'


def fetch_mol3d_text(source_url: str, config) -> str:
    '''Download one 3D MOL/SDF text block.

    Args:
        source_url: WebBook 3D structure URL from the NistChemPy index.
        config: NistChemPy request configuration.

    Returns:
        Downloaded text with normalized line endings.

    Raises:
        RuntimeError: If the response is not OK or the file is empty.

    '''
    response = request_nist(source_url, config=config)
    if not response.ok:
        status = getattr(response.response, 'status_code', 'unknown')
        raise RuntimeError(f'failed to load 3D structure, HTTP status {status}')
    if not response.text or not response.text.strip():
        raise RuntimeError('empty 3D structure response')

    return response.text.replace('\r\n', '\n').replace('\r', '\n')


def write_manifest(
    path_manifest: str | Path,
    compound_id: str,
    status: str,
    n_files: int,
    archive_members: list[str],
    source_url: str,
    message: str = '',
) -> None:
    '''Append one 3D-structure download row to the manifest.'''
    append_manifest_row(
        path_manifest,
        {
            'retrieved_at': utc_now(),
            'compound_id': compound_id,
            'data_type': DATA_TYPE,
            'status': status,
            'n_files': n_files,
            'archive_members': format_archive_members(archive_members),
            'source_url': source_url,
            'source_database': SOURCE_DATABASE,
            'rights_status': RIGHTS_STATUS,
            'message': message,
        },
        columns=MANIFEST_COLUMNS,
    )


def download_mol3d(
    path_out: str | Path,
    path_manifest: str | Path,
    crawl_delay: float = 1.0,
    timeout: float = 30.0,
    max_attempts: int = 3,
    index_path: str | Path | None = None,
    ids: list[str] | None = None,
    limit: int | None = None,
) -> None:
    '''Download available 3D structures into a local raw MOL ZIP archive.

    Args:
        path_out: Output raw MOL ZIP archive path.
        path_manifest: CSV manifest path.
        crawl_delay: Delay after HTTP requests, in seconds.
        timeout: Per-request timeout, in seconds.
        max_attempts: Maximum number of request attempts.
        index_path: Optional NistChemPy local index directory or CSV path.
        ids: Optional ordered list of compound IDs to process.
        limit: Optional maximum number of index rows to process.

    '''
    config = make_request_config(crawl_delay, timeout, max_attempts)
    df = load_webbook_index(index_path)
    rows = filter_index_rows(df, SOURCE_COLUMN, ids=ids, limit=limit)

    path_out = Path(path_out)
    path_manifest = Path(path_manifest)
    ensure_parent(path_out)
    ensure_parent(path_manifest)

    try:
        archive_state = mol_archive_members_by_compound(
            path_out, require_nonempty=True
        )
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f'Invalid ZIP archive: {path_out}') from exc

    completed_ids = completed_ids_for_download(
        path_manifest,
        data_type=DATA_TYPE,
        path_archive=path_out,
        archive_state=archive_state,
    )

    for _, row in tqdm(rows.iterrows(), total=len(rows)):
        compound_id = str(row['ID'])
        source_url = str(row[SOURCE_COLUMN])
        member_name = f'{compound_id}.mol'

        if compound_id in completed_ids:
            continue

        archive_members = []
        existing_for_compound = archive_state.setdefault(compound_id, {})
        existing_member = existing_for_compound.get(member_name)

        try:
            if existing_member is not None:
                archive_members.append(existing_member)
            else:
                mol_text = fetch_mol3d_text(source_url, config)
                with zipfile.ZipFile(
                    path_out, 'a', compression=zipfile.ZIP_DEFLATED
                ) as zipf:
                    zipf.writestr(member_name, mol_text)
                existing_for_compound[member_name] = member_name
                archive_members.append(member_name)

            write_manifest(
                path_manifest,
                compound_id,
                'done',
                len(archive_members),
                archive_members,
                source_url,
            )
        except (KeyboardInterrupt, SystemExit):
            tqdm.write('The code execution was interrupted')
            raise
        except Exception as exc:
            tqdm.write(f'Error while processing compound {compound_id}: {exc}')
            write_manifest(
                path_manifest,
                compound_id,
                'error',
                len(archive_members),
                archive_members,
                source_url,
                str(exc),
            )


def get_arguments() -> argparse.Namespace:
    '''Parse command-line arguments.

    Returns:
        Parsed CLI arguments.

    '''
    parser = argparse.ArgumentParser(
        description='Download local NIST Chemistry WebBook 3D MOL archive.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--out',
        default=DEFAULT_OUTPUT,
        help='output raw MOL ZIP archive path',
    )
    parser.add_argument(
        '--manifest',
        default=DEFAULT_MANIFEST,
        help='CSV manifest path',
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
        help='maximum number of index rows to process',
    )
    parser.add_argument(
        '--crawl-delay',
        type=float,
        default=1.0,
        help='pause after HTTP requests, seconds',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=30.0,
        help='per-request timeout, seconds',
    )
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=3,
        help='maximum request attempts',
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
    if args.crawl_delay < 0:
        raise ValueError(f'--crawl-delay must be non-negative: {args.crawl_delay}')
    if args.timeout <= 0:
        raise ValueError(f'--timeout must be positive: {args.timeout}')
    if args.max_attempts <= 0:
        raise ValueError(f'--max-attempts must be positive: {args.max_attempts}')


def main() -> None:
    '''Download local raw 3D MOL archive.'''
    args = get_arguments()
    check_arguments(args)
    require_data_terms_acknowledgement(args.accept_data_terms)

    ids = split_id_argument(args.ids)

    print('\nDownloading 3D MOL files ...')
    print(f'Output archive: {args.out}')
    print(f'Manifest: {args.manifest}')

    download_mol3d(
        args.out,
        args.manifest,
        crawl_delay=args.crawl_delay,
        timeout=args.timeout,
        max_attempts=args.max_attempts,
        index_path=args.index_path,
        ids=ids,
        limit=args.limit,
    )
    print()


if __name__ == '__main__':
    main()
