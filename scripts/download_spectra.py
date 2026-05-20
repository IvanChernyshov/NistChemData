'''Download local NIST Chemistry WebBook spectrum archives.'''

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tqdm import tqdm

from common import (
    MANIFEST_COLUMNS,
    NIST_SEARCH_URL,
    RIGHTS_STATUS,
    SOURCE_DATABASE,
    append_manifest_row,
    completed_ids_for_download,
    ensure_parent,
    existing_zip_members,
    filter_index_rows,
    format_archive_members,
    load_webbook_index,
    make_request_config,
    normalize_spectrum_type,
    request_nist,
    require_data_terms_acknowledgement,
    split_id_argument,
    spectrum_archive_members_by_compound,
    spectrum_download_type,
    spectrum_search_column,
    utc_now,
)


DEFAULT_OUTPUTS = {
    'IR': 'local-data/raw/spectra/nist_IR.zip',
    'TZ': 'local-data/raw/spectra/nist_TZ.zip',
    'MS': 'local-data/raw/spectra/nist_MS.zip',
    'UV': 'local-data/raw/spectra/nist_UV.zip',
}

DEFAULT_MANIFESTS = {
    'IR': 'local-data/manifests/nist_IR_manifest.csv',
    'TZ': 'local-data/manifests/nist_TZ_manifest.csv',
    'MS': 'local-data/manifests/nist_MS_manifest.csv',
    'UV': 'local-data/manifests/nist_UV_manifest.csv',
}


def extract_spectrum_indexes(soup) -> list[str]:
    '''Extract unique spectrum indexes from a WebBook spectrum page.

    Args:
        soup: BeautifulSoup object from a NistChemPy response.

    Returns:
        Sorted list of unique spectrum indexes as strings.

    '''
    if soup is None:
        return []

    indexes = []
    refs = soup.find_all(attrs={'href': re.compile('Index=')})
    for ref in refs:
        href = ref.attrs.get('href')
        if not href:
            continue
        query = parse_qs(urlparse(href).query)
        indexes.extend(query.get('Index', []))

    return sorted(set(indexes), key=_index_sort_key)


def _index_sort_key(value: str) -> tuple[int, str]:
    '''Return a stable natural-ish sort key for WebBook spectrum indexes.'''
    try:
        return (int(value), value)
    except ValueError:
        return (sys.maxsize, value)


def fetch_spectrum_indexes(source_url: str, config) -> list[str]:
    '''Fetch a spectrum section page and return available spectrum indexes.

    Args:
        source_url: WebBook section URL from the NistChemPy index.
        config: NistChemPy request configuration.

    Returns:
        Sorted list of spectrum indexes.

    Raises:
        RuntimeError: If the spectrum section page cannot be loaded.

    '''
    response = request_nist(source_url, config=config)
    if not response.ok:
        status = getattr(response.response, 'status_code', 'unknown')
        raise RuntimeError(f'failed to load spectrum page, HTTP status {status}')

    return extract_spectrum_indexes(response.soup)


def fetch_spectrum_jdx(compound_id: str, spec_type: str, spec_idx: str, config) -> str:
    '''Download one JDX spectrum file.

    Args:
        compound_id: NIST Chemistry WebBook compound ID.
        spec_type: Spectrum type: IR, TZ, MS, or UV.
        spec_idx: Spectrum index on the WebBook page.
        config: NistChemPy request configuration.

    Returns:
        JDX text.

    Raises:
        RuntimeError: If the JDX file cannot be loaded.

    '''
    params = {
        'JCAMP': compound_id,
        'Index': spec_idx,
        'Type': spectrum_download_type(spec_type),
    }
    response = request_nist(NIST_SEARCH_URL, params=params, config=config)
    if not response.ok:
        status = getattr(response.response, 'status_code', 'unknown')
        raise RuntimeError(
            f'failed to load {spec_type} spectrum {spec_idx}, HTTP status {status}'
        )
    if not response.text:
        raise RuntimeError(f'empty {spec_type} spectrum {spec_idx}')

    return response.text


def write_manifest(
    path_manifest: str | Path,
    compound_id: str,
    data_type: str,
    status: str,
    n_files: int,
    archive_members: list[str],
    source_url: str,
    message: str = '',
) -> None:
    '''Append one spectrum-download row to the manifest.'''
    append_manifest_row(
        path_manifest,
        {
            'retrieved_at': utc_now(),
            'compound_id': compound_id,
            'data_type': data_type,
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


def download_spectra(
    path_out: str | Path,
    spec_type: str,
    path_manifest: str | Path,
    crawl_delay: float = 1.0,
    timeout: float = 30.0,
    max_attempts: int = 3,
    index_path: str | Path | None = None,
    ids: list[str] | None = None,
    limit: int | None = None,
    verify_existing_archive: bool = False,
) -> None:
    '''Download available spectra of one type into a local ZIP archive.

    Args:
        path_out: Output ZIP archive path.
        spec_type: Spectrum type: IR, TZ, MS, or UV.
        path_manifest: CSV manifest path.
        crawl_delay: Delay after HTTP requests, in seconds.
        timeout: Per-request timeout, in seconds.
        max_attempts: Maximum number of request attempts.
        index_path: Optional NistChemPy local index directory or CSV path.
        ids: Optional ordered list of compound IDs to process.
        limit: Optional maximum number of index rows to process.
        verify_existing_archive: If true, check source pages for all selected
            compounds and download only missing archive members. If false,
            skip valid completed manifest rows and archive-only compounds with
            no manifest state.

    '''
    spec_type = normalize_spectrum_type(spec_type)
    data_type = f'{spec_type}_spectrum'
    column = spectrum_search_column(spec_type)

    config = make_request_config(crawl_delay, timeout, max_attempts)
    df = load_webbook_index(index_path)
    rows = filter_index_rows(df, column, ids=ids, limit=limit)

    path_out = Path(path_out)
    path_manifest = Path(path_manifest)
    ensure_parent(path_out)
    ensure_parent(path_manifest)

    try:
        archive_state = spectrum_archive_members_by_compound(
            path_out, spec_type, require_nonempty=True
        )
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f'Invalid ZIP archive: {path_out}') from exc

    existing_members = existing_zip_members(path_out, require_nonempty=True)
    completed_ids = set()
    if not verify_existing_archive:
        completed_ids = completed_ids_for_download(
            path_manifest,
            data_type=data_type,
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
            indexes = fetch_spectrum_indexes(source_url, config)
            if not indexes:
                tqdm.write(f'No {spec_type} spectrum indexes found for {compound_id}')
                write_manifest(
                    path_manifest,
                    compound_id,
                    data_type,
                    'no_data',
                    0,
                    [],
                    source_url,
                    'no spectrum indexes found on source page',
                )
                continue

            with zipfile.ZipFile(path_out, 'a', compression=zipfile.ZIP_DEFLATED) as zipf:
                for spec_idx in indexes:
                    member_name = f'{compound_id}_{spec_type}_{spec_idx}.jdx'
                    existing_member = existing_for_compound.get(member_name)
                    if existing_member is not None:
                        archive_members.append(existing_member)
                        continue

                    if member_name in existing_members:
                        archive_members.append(member_name)
                        existing_for_compound[member_name] = member_name
                        continue

                    jdx_text = fetch_spectrum_jdx(
                        compound_id,
                        spec_type,
                        spec_idx,
                        config,
                    )
                    zipf.writestr(member_name, jdx_text)
                    existing_members.add(member_name)
                    existing_for_compound[member_name] = member_name
                    archive_members.append(member_name)

            write_manifest(
                path_manifest,
                compound_id,
                data_type,
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
                data_type,
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
        description='Download local NIST Chemistry WebBook spectrum archives.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('spec_type', help='spectrum type: IR, TZ, MS, or UV')
    parser.add_argument(
        '--out',
        help='output ZIP archive path; defaults to local-data/raw/spectra',
    )
    parser.add_argument(
        '--manifest',
        help='CSV manifest path; defaults to local-data/manifests',
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
            'check source pages even when matching JDX files already exist; '
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
    args.spec_type = normalize_spectrum_type(args.spec_type)

    if args.out is None:
        args.out = DEFAULT_OUTPUTS[args.spec_type]
    if args.manifest is None:
        args.manifest = DEFAULT_MANIFESTS[args.spec_type]

    if args.limit is not None and args.limit <= 0:
        raise ValueError(f'--limit must be positive: {args.limit}')
    if args.crawl_delay < 0:
        raise ValueError(f'--crawl-delay must be non-negative: {args.crawl_delay}')
    if args.timeout <= 0:
        raise ValueError(f'--timeout must be positive: {args.timeout}')
    if args.max_attempts <= 0:
        raise ValueError(f'--max-attempts must be positive: {args.max_attempts}')


def main() -> None:
    '''Download local raw spectrum archives.'''
    args = get_arguments()
    check_arguments(args)
    require_data_terms_acknowledgement(args.accept_data_terms)

    ids = split_id_argument(args.ids)

    print(f'\nDownloading {args.spec_type} spectra ...')
    print(f'Output archive: {args.out}')
    print(f'Manifest: {args.manifest}')

    download_spectra(
        args.out,
        args.spec_type,
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
