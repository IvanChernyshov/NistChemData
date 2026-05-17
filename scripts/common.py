'''Shared helpers for NistChemData local reconstruction scripts.'''

from __future__ import annotations

import csv
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import nistchempy as nist
from nistchempy.requests import SEARCH_URL, make_nist_request


ACK_ENV_VAR = 'NISTCHEMDATA_ACCEPT_DATA_TERMS'
SOURCE_DATABASE = 'NIST Chemistry WebBook / SRD 69'
RIGHTS_STATUS = 'SRD_DERIVED_REUSE_NOT_CONFIRMED'
NIST_SEARCH_URL = SEARCH_URL

DATA_RIGHTS_MESSAGE = '''\
Generated files may be derived from the NIST Chemistry WebBook / SRD 69 and/or
source-literature-origin collections exposed through WebBook records.

The repository MIT license applies only to original scripts and documentation.
It does not grant permission to redistribute generated data files.
'''

SPECTRUM_SEARCH_KEYS = {
    'IR': 'cIR',
    'TZ': 'cTZ',
    'MS': 'cMS',
    'UV': 'cUV',
}

SPECTRUM_DOWNLOAD_TYPES = {
    'IR': 'IR',
    'TZ': 'THz',
    'MS': 'Mass',
    'UV': 'UVVis',
}

MANIFEST_COLUMNS = [
    'retrieved_at',
    'compound_id',
    'data_type',
    'status',
    'n_files',
    'archive_members',
    'source_url',
    'source_database',
    'rights_status',
    'message',
]


def utc_now() -> str:
    '''Return the current UTC timestamp in ISO-8601 format.

    Returns:
        Current UTC timestamp with seconds precision.

    '''
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def require_data_terms_acknowledgement(accepted: bool) -> None:
    '''Require explicit acknowledgement before generating local artifacts.

    Args:
        accepted: Whether the user passed the CLI acknowledgement flag.

    Raises:
        SystemExit: If the acknowledgement was not provided through the CLI
            flag or through the NISTCHEMDATA_ACCEPT_DATA_TERMS environment
            variable.

    '''
    env_accepted = os.environ.get(ACK_ENV_VAR, '').strip().lower()
    env_accepted = env_accepted in {'1', 'true', 'yes', 'y'}
    if accepted or env_accepted:
        return

    raise SystemExit(
        DATA_RIGHTS_MESSAGE.strip()
        + '\n\nPass --accept-data-terms or set '
        + f'{ACK_ENV_VAR}=1 to create local generated files.'
    )


def make_request_config(
    crawl_delay: float,
    timeout: float,
    max_attempts: int,
) -> nist.RequestConfig:
    '''Create a NistChemPy request configuration.

    Args:
        crawl_delay: Delay after requests, in seconds.
        timeout: Per-request timeout, in seconds.
        max_attempts: Maximum number of request attempts.

    Returns:
        NistChemPy request configuration.

    '''
    return nist.RequestConfig(
        delay=crawl_delay,
        max_attempts=max_attempts,
        kwargs={'timeout': timeout},
    )


def load_webbook_index() -> Any:
    '''Load the current NistChemPy WebBook index.

    This is a temporary compatibility layer. Current NistChemPy versions expose a
    package-internal index through ``nist.get_all_data()``. After NistChemPy is
    refactored to a user-local index/cache, this function should be the only
    place that needs to change in NistChemData.

    Returns:
        Pandas DataFrame returned by ``nist.get_all_data()``.

    '''
    return nist.get_all_data()


def request_nist(
    url: str,
    params: Mapping[str, Any] | None = None,
    config: Any | None = None,
) -> Any:
    '''Send a GET request through NistChemPy's request wrapper.

    Args:
        url: Request URL.
        params: Optional GET parameters.
        config: Optional NistChemPy request configuration.

    Returns:
        NistChemPy response wrapper.

    '''
    return make_nist_request(url, dict(params or {}), config=config)


def get_search_column(search_key: str) -> str:
    '''Return the WebBook index column corresponding to a NistChemPy key.

    Args:
        search_key: Short NistChemPy search key, such as ``cIR`` or ``cGC``.

    Returns:
        Column name in the NistChemPy WebBook index.

    Raises:
        ValueError: If the key is not known to NistChemPy.

    '''
    column = nist.get_search_parameters().get(search_key)
    if column is None:
        raise ValueError(f'Unknown NistChemPy search key: {search_key}')
    return column


def normalize_spectrum_type(spec_type: str) -> str:
    '''Normalize and validate a WebBook spectrum type.

    Args:
        spec_type: Spectrum type, case-insensitive. Supported values are
            ``IR``, ``TZ``, ``MS``, and ``UV``.

    Returns:
        Uppercase normalized spectrum type.

    Raises:
        ValueError: If the spectrum type is unsupported.

    '''
    normalized = spec_type.upper()
    if normalized not in SPECTRUM_SEARCH_KEYS:
        allowed = ', '.join(sorted(SPECTRUM_SEARCH_KEYS))
        raise ValueError(f'spec_type must be one of {allowed}: {spec_type}')
    return normalized


def spectrum_search_column(spec_type: str) -> str:
    '''Return the WebBook index column for a spectrum type.

    Args:
        spec_type: Spectrum type: ``IR``, ``TZ``, ``MS``, or ``UV``.

    Returns:
        Column name in the NistChemPy WebBook index.

    '''
    spec_type = normalize_spectrum_type(spec_type)
    return get_search_column(SPECTRUM_SEARCH_KEYS[spec_type])


def spectrum_download_type(spec_type: str) -> str:
    '''Return the WebBook JCAMP ``Type`` parameter for a spectrum type.

    Args:
        spec_type: Spectrum type: ``IR``, ``TZ``, ``MS``, or ``UV``.

    Returns:
        WebBook JCAMP ``Type`` value.

    '''
    spec_type = normalize_spectrum_type(spec_type)
    return SPECTRUM_DOWNLOAD_TYPES[spec_type]


def filter_index_rows(
    df: Any,
    column: str,
    ids: Sequence[str] | None = None,
    limit: int | None = None,
) -> Any:
    '''Filter a WebBook index table for rows with a non-empty source column.

    Args:
        df: Pandas DataFrame returned by ``load_webbook_index``.
        column: Column that should contain source URLs or availability flags.
        ids: Optional ordered list of compound IDs to keep.
        limit: Optional maximum number of rows to return.

    Returns:
        Filtered DataFrame sorted by compound ID.

    Raises:
        ValueError: If the required column is absent.

    '''
    if column not in df.columns:
        raise ValueError(f'Missing required WebBook index column: {column}')

    mask = df[column].notna() & df[column].astype(str).str.strip().ne('')
    out = df.loc[mask].copy()

    if ids is not None:
        id_order = {compound_id: idx for idx, compound_id in enumerate(ids)}
        out = out.loc[out['ID'].isin(id_order)]
        out['_order'] = out['ID'].map(id_order)
        out = out.sort_values('_order').drop(columns=['_order'])
    else:
        out = out.sort_values('ID')

    if limit is not None:
        out = out.head(limit)

    return out.reset_index(drop=True)


def ensure_parent(path: str | Path) -> None:
    '''Create a file's parent directory if needed.

    Args:
        path: File path whose parent directory should exist.

    '''
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def ensure_dir(path: str | Path) -> None:
    '''Create a directory if needed.

    Args:
        path: Directory path to create.

    '''
    Path(path).mkdir(parents=True, exist_ok=True)


def existing_zip_members(path_zip: str | Path) -> set[str]:
    '''Return archive member names already present in a ZIP file.

    Args:
        path_zip: Path to the ZIP archive.

    Returns:
        Set of archive member names. Returns an empty set if the archive does
        not yet exist.

    '''
    path_zip = Path(path_zip)
    if not path_zip.exists():
        return set()

    with zipfile.ZipFile(path_zip, 'r') as zipf:
        return set(zipf.namelist())


def zip_writestr_if_missing(
    path_zip: str | Path,
    member_name: str,
    data: str | bytes,
    overwrite: bool = False,
) -> bool:
    '''Write one member to a ZIP archive unless it already exists.

    Args:
        path_zip: Path to the ZIP archive.
        member_name: Member name inside the archive.
        data: Text or bytes to write.
        overwrite: Whether to replace an existing member. Replacing a ZIP member
            is implemented by appending a duplicate member with the same name;
            for normal workflows, keep this as ``False``.

    Returns:
        ``True`` if data were written, otherwise ``False``.

    '''
    path_zip = Path(path_zip)
    ensure_parent(path_zip)

    if not overwrite and member_name in existing_zip_members(path_zip):
        return False

    mode = 'a' if path_zip.exists() else 'w'
    with zipfile.ZipFile(path_zip, mode, compression=zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(member_name, data)

    return True


def format_archive_members(members: Iterable[str]) -> str:
    '''Format archive member names for a manifest cell.

    Args:
        members: Archive member names.

    Returns:
        Semicolon-separated member list.

    '''
    return ';'.join(str(member) for member in members)


def append_manifest_row(
    path_manifest: str | Path,
    row: Mapping[str, Any],
    columns: Sequence[str] = MANIFEST_COLUMNS,
) -> None:
    '''Append one row to a CSV manifest.

    Args:
        path_manifest: Path to the manifest CSV file.
        row: Mapping with manifest values.
        columns: Column order to use. Missing values are written as empty
            strings.

    '''
    path_manifest = Path(path_manifest)
    ensure_parent(path_manifest)
    write_header = not path_manifest.exists()

    with path_manifest.open('a', newline='', encoding='utf-8') as out_file:
        writer = csv.DictWriter(out_file, fieldnames=list(columns))
        if write_header:
            writer.writeheader()
        writer.writerow({column: row.get(column, '') for column in columns})


def read_manifest_rows(path_manifest: str | Path) -> list[dict[str, str]]:
    '''Read manifest rows from a CSV file.

    Args:
        path_manifest: Path to the manifest CSV file.

    Returns:
        List of manifest rows. Returns an empty list if the file does not exist.

    '''
    path_manifest = Path(path_manifest)
    if not path_manifest.exists():
        return []

    with path_manifest.open(newline='', encoding='utf-8') as in_file:
        return list(csv.DictReader(in_file))


def completed_ids_from_manifest(
    path_manifest: str | Path,
    data_type: str | None = None,
) -> set[str]:
    '''Return compound IDs marked as successfully completed in a manifest.

    Args:
        path_manifest: Path to the manifest CSV file.
        data_type: Optional data type filter.

    Returns:
        Set of compound IDs with ``status == 'done'``.

    '''
    completed = set()
    for row in read_manifest_rows(path_manifest):
        if row.get('status') != 'done':
            continue
        if data_type is not None and row.get('data_type') != data_type:
            continue
        compound_id = row.get('compound_id')
        if compound_id:
            completed.add(compound_id)
    return completed


def safe_filename_component(value: Any, default: str = 'unknown') -> str:
    '''Convert a value to a conservative filename component.

    Args:
        value: Value to sanitize.
        default: Fallback string for empty values.

    Returns:
        Sanitized filename component containing only ASCII letters, digits,
        underscores, periods, hyphens, plus signs, equals signs, and
        parentheses.

    '''
    text = '' if value is None else str(value)
    text = text.encode('ascii', errors='ignore').decode('ascii')
    text = re.sub(r'[^A-Za-z0-9_.\-+=()]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('._-')
    return text or default


def split_id_argument(value: str | None) -> list[str] | None:
    '''Parse a comma-separated compound-ID CLI argument.

    Args:
        value: Comma-separated compound IDs, or ``None``.

    Returns:
        List of stripped compound IDs, or ``None`` if no value was supplied.

    '''
    if value is None:
        return None

    ids = [item.strip() for item in value.split(',')]
    return [item for item in ids if item]
