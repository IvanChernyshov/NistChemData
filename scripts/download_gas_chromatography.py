'''Download local NIST Chemistry WebBook gas-chromatography parts.'''

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from nistchempy.parsing import (
    get_chromatography_table_refs,
    parse_chromatography_table,
)
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
    gc_archive_members_by_compound,
    get_search_column,
    legacy_gc_member_name,
    load_webbook_index,
    make_request_config,
    request_nist,
    require_data_terms_acknowledgement,
    split_id_argument,
    utc_now,
)


DEFAULT_OUTPUT = 'local-data/raw/nist_gc_parts.zip'
DEFAULT_MANIFEST = 'local-data/manifests/nist_gc_manifest.csv'
DATA_TYPE = 'gas_chromatography'
SEARCH_KEY = 'cGC'


def fetch_gc_table_urls(source_url: str, config) -> list[str]:
    '''Fetch a WebBook GC section page and return large-table URLs.

    Args:
        source_url: WebBook gas-chromatography section URL.
        config: NistChemPy request configuration.

    Returns:
        List of large-format GC table URLs.

    Raises:
        RuntimeError: If the section page cannot be loaded.

    '''
    response = request_nist(source_url, config=config)
    if not response.ok:
        status = getattr(response.response, 'status_code', 'unknown')
        raise RuntimeError(f'failed to load GC page, HTTP status {status}')
    if response.soup is None:
        raise RuntimeError('GC page response is not HTML')

    return get_chromatography_table_refs(response.soup)


def fetch_gc_table(table_url: str, config) -> dict:
    '''Fetch and parse one large-format GC table.

    Args:
        table_url: WebBook large-format GC table URL.
        config: NistChemPy request configuration.

    Returns:
        Dictionary returned by NistChemPy's GC table parser.

    Raises:
        RuntimeError: If the table page cannot be loaded or parsed.

    '''
    response = request_nist(table_url, config=config)
    if not response.ok:
        status = getattr(response.response, 'status_code', 'unknown')
        raise RuntimeError(f'failed to load GC table, HTTP status {status}')
    if response.soup is None:
        raise RuntimeError('GC table response is not HTML')

    return parse_chromatography_table(response.soup)


def table_to_csv(info: dict) -> str:
    '''Convert parsed GC table info to CSV text.

    Args:
        info: Parsed GC table info containing a pandas DataFrame under ``data``.

    Returns:
        CSV text without an index column.

    '''
    return info['data'].to_csv(index=False)


def write_manifest(
    path_manifest: str | Path,
    compound_id: str,
    status: str,
    n_files: int,
    archive_members: list[str],
    source_url: str,
    message: str = '',
) -> None:
    '''Append one GC-download row to the manifest.'''
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


def download_gas_chromatography(
    path_out: str | Path,
    path_manifest: str | Path,
    crawl_delay: float = 1.0,
    timeout: float = 30.0,
    max_attempts: int = 3,
    index_path: str | Path | None = None,
    ids: list[str] | None = None,
    limit: int | None = None,
    verify_existing_archive: bool = False,
) -> None:
    '''Download available GC tables into a local raw parts ZIP archive.

    Args:
        path_out: Output raw GC parts ZIP archive path.
        path_manifest: CSV manifest path.
        crawl_delay: Delay after HTTP requests, in seconds.
        timeout: Per-request timeout, in seconds.
        max_attempts: Maximum number of request attempts.
        index_path: Optional NistChemPy local index directory or CSV path.
        ids: Optional ordered list of compound IDs to process.
        limit: Optional maximum number of index rows to process.
        verify_existing_archive: If true, check source pages for all selected
            compounds and download only missing GC table parts. If false, skip
            valid completed manifest rows and archive-only compounds with no
            manifest state.

    '''
    config = make_request_config(crawl_delay, timeout, max_attempts)
    df = load_webbook_index(index_path)
    column = get_search_column(SEARCH_KEY)
    rows = filter_index_rows(df, column, ids=ids, limit=limit)

    path_out = Path(path_out)
    path_manifest = Path(path_manifest)
    ensure_parent(path_out)
    ensure_parent(path_manifest)

    try:
        archive_state = gc_archive_members_by_compound(
            path_out, require_nonempty=True
        )
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f'Invalid ZIP archive: {path_out}') from exc

    completed_ids = set()
    if not verify_existing_archive:
        completed_ids = completed_ids_for_download(
            path_manifest,
            data_type=DATA_TYPE,
            path_archive=path_out,
            archive_state=archive_state,
        )

    for _, row in tqdm(rows.iterrows(), total=len(rows)):
        compound_id = str(row['ID'])
        source_url = str(row[column])

        if compound_id in completed_ids:
            continue

        archive_members = []
        existing_for_compound = archive_state.setdefault(compound_id, {})

        try:
            table_urls = fetch_gc_table_urls(source_url, config)
            if not table_urls:
                tqdm.write(f'No GC table URLs found for {compound_id}')
                write_manifest(
                    path_manifest,
                    compound_id,
                    'no_data',
                    0,
                    [],
                    source_url,
                    'no large-format GC table URLs found on source page',
                )
                continue

            with zipfile.ZipFile(
                path_out, 'a', compression=zipfile.ZIP_DEFLATED
            ) as zipf:
                for table_url in table_urls:
                    info = fetch_gc_table(table_url, config)
                    member_name = legacy_gc_member_name(
                        compound_id,
                        info['ri_type'],
                        info['column_type'],
                        info['temp_regime'],
                    )
                    existing_member = existing_for_compound.get(member_name)
                    if existing_member is not None:
                        archive_members.append(existing_member)
                        continue

                    csv_text = table_to_csv(info)
                    zipf.writestr(member_name, csv_text)
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
        description='Download local NIST Chemistry WebBook GC table parts.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--out',
        default=DEFAULT_OUTPUT,
        help='output raw GC parts ZIP archive path',
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
        '--verify-existing-archive',
        action='store_true',
        help=(
            'check source pages even when matching GC CSV files already exist; '
            'existing files are reused and only missing files are downloaded'
        ),
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
    '''Download local raw GC table parts archive.'''
    args = get_arguments()
    check_arguments(args)
    require_data_terms_acknowledgement(args.accept_data_terms)

    ids = split_id_argument(args.ids)

    print('\nDownloading GC table parts ...')
    print(f'Output archive: {args.out}')
    print(f'Manifest: {args.manifest}')

    download_gas_chromatography(
        args.out,
        args.manifest,
        crawl_delay=args.crawl_delay,
        timeout=args.timeout,
        max_attempts=args.max_attempts,
        index_path=args.index_path,
        ids=ids,
        limit=args.limit,
        verify_existing_archive=args.verify_existing_archive,
    )
    print()


if __name__ == '__main__':
    main()
