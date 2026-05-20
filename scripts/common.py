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


def load_webbook_index(path: str | Path | None = None) -> Any:
    '''Load a user-local NistChemPy WebBook index table.

    Args:
        path: Optional NistChemPy local index directory or CSV path. If omitted,
            NistChemPy resolves its default path, including the
            ``NISTCHEMPY_INDEX_PATH`` environment variable.

    Returns:
        Pandas DataFrame returned by ``nist.get_local_index(path).to_dataframe()``.

    Raises:
        RuntimeError: If the installed NistChemPy version does not expose the
            2.0 local-index API.

    '''
    try:
        index = nist.get_local_index(path)
    except AttributeError as exc:
        raise RuntimeError(
            'NistChemData requires NistChemPy 2.0.0 or newer with the '
            'user-local WebBook index API.'
        ) from exc
    return index.to_dataframe()


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


def zip_member_sizes(path_zip: str | Path) -> dict[str, int]:
    '''Return archive member sizes keyed by member name.

    Args:
        path_zip: Path to the ZIP archive.

    Returns:
        Mapping from archive member names to uncompressed sizes. Returns an
        empty mapping if the archive does not exist. If a ZIP contains duplicate
        member names, the last entry wins, which matches the usual append-based
        repair behavior used by these scripts.

    Raises:
        zipfile.BadZipFile: If the archive exists but is not a valid ZIP file.

    '''
    path_zip = Path(path_zip)
    if not path_zip.exists():
        return {}

    with zipfile.ZipFile(path_zip, 'r') as zipf:
        return {info.filename: info.file_size for info in zipf.infolist()}


def existing_zip_members(
    path_zip: str | Path,
    require_nonempty: bool = False,
) -> set[str]:
    '''Return archive member names already present in a ZIP file.

    Args:
        path_zip: Path to the ZIP archive.
        require_nonempty: If true, return only members with nonzero size.

    Returns:
        Set of archive member names. Returns an empty set if the archive does
        not yet exist.

    '''
    members = zip_member_sizes(path_zip)
    if require_nonempty:
        return {name for name, size in members.items() if size > 0}
    return set(members)


def archive_members_by_basename(
    path_zip: str | Path,
    require_nonempty: bool = True,
) -> dict[str, str]:
    '''Return ZIP members keyed by their root-level basename.

    This helper lets reconstruction scripts reuse older archives whose members
    were stored under a top-level directory, for example
    ``TZ/B7000012_TZ_0.jdx`` instead of ``B7000012_TZ_0.jdx``. The values are
    the actual member paths present in the archive, so manifests can still
    validate the archive exactly.

    Args:
        path_zip: Path to the ZIP archive.
        require_nonempty: If true, zero-size members are ignored.

    Returns:
        Mapping from basename to actual ZIP member name. If duplicate basenames
        occur, the last non-empty member in the archive wins.

    '''
    members = zip_member_sizes(path_zip)
    out: dict[str, str] = {}
    for member, size in members.items():
        if member.endswith('/'):
            continue
        if require_nonempty and size <= 0:
            continue

        basename = Path(member).name
        if basename:
            out[basename] = member

    return out


def spectrum_archive_members_by_compound(
    path_zip: str | Path,
    spec_type: str,
    require_nonempty: bool = True,
) -> dict[str, dict[str, str]]:
    '''Group existing spectrum ZIP members by compound ID.

    The returned nested mapping has this form::

        {compound_id: {canonical_basename: actual_archive_member}}

    For example, an existing legacy member ``TZ/B7000012_TZ_0.jdx`` is returned
    as ``{'B7000012': {'B7000012_TZ_0.jdx': 'TZ/B7000012_TZ_0.jdx'}}``.
    This makes existing archives usable for resume without forcing immediate
    repackaging.

    Args:
        path_zip: Path to the ZIP archive.
        spec_type: Spectrum type: ``IR``, ``TZ``, ``MS``, or ``UV``.
        require_nonempty: If true, zero-size members are ignored.

    Returns:
        Mapping from compound ID to existing archive members.

    '''
    spec_type = normalize_spectrum_type(spec_type)
    pattern = re.compile(
        rf'^(?P<compound_id>.+)_{re.escape(spec_type)}_(?P<index>.+)\.jdx$',
        flags=re.IGNORECASE,
    )

    grouped: dict[str, dict[str, str]] = {}
    for basename, member in archive_members_by_basename(
        path_zip, require_nonempty=require_nonempty
    ).items():
        match = pattern.match(basename)
        if match is None:
            continue

        compound_id = match.group('compound_id')
        grouped.setdefault(compound_id, {})[basename] = member

    return grouped


def mol_archive_members_by_compound(
    path_zip: str | Path,
    require_nonempty: bool = True,
) -> dict[str, dict[str, str]]:
    '''Group existing 3D MOL ZIP members by compound ID.

    The returned nested mapping has this form::

        {compound_id: {canonical_basename: actual_archive_member}}

    For example, an existing legacy member ``mol3d/C71432.mol`` is returned as
    ``{'C71432': {'C71432.mol': 'mol3d/C71432.mol'}}``. This lets local raw
    MOL archives be reused even if files were stored under a top-level folder.

    Args:
        path_zip: Path to the ZIP archive.
        require_nonempty: If true, zero-size members are ignored.

    Returns:
        Mapping from compound ID to existing archive members.

    '''
    pattern = re.compile(r'^(?P<compound_id>.+)\.mol$', flags=re.IGNORECASE)

    grouped: dict[str, dict[str, str]] = {}
    for basename, member in archive_members_by_basename(
        path_zip, require_nonempty=require_nonempty
    ).items():
        match = pattern.match(basename)
        if match is None:
            continue

        compound_id = match.group('compound_id')
        canonical = f'{compound_id}.mol'
        grouped.setdefault(compound_id, {})[canonical] = member

    return grouped


def _clean_legacy_gc_filename_component(value: Any) -> str:
    '''Clean one GC filename component while preserving old-style names.'''
    text = '' if value is None else str(value)
    text = text.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
    text = text.replace('/', '-').replace('\\', '-')
    text = text.replace(';', ',')
    text = re.sub(r' +', ' ', text).strip()
    return text or 'unknown'


def legacy_gc_member_name(
    compound_id: Any,
    ri_type: Any,
    column_type: Any,
    temp_regime: Any,
) -> str:
    '''Return the old-compatible GC CSV archive member name.

    The name intentionally follows the historical NistChemData/NistChemPy
    convention, for example::

        R32777_Kovats' RI_non-polar column_isothermal.csv

    Only path separators and control-like whitespace are normalized so existing
    old downloads can be repacked and reused without renaming.

    Args:
        compound_id: NIST Chemistry WebBook compound ID.
        ri_type: Retention-index type.
        column_type: Column polarity/type label.
        temp_regime: Temperature-regime label.

    Returns:
        Old-compatible CSV member basename.

    '''
    parts = [compound_id, ri_type, column_type, temp_regime]
    cleaned = [_clean_legacy_gc_filename_component(part) for part in parts]
    return '_'.join(cleaned) + '.csv'


def parse_legacy_gc_member_name(member_name: str) -> dict[str, str]:
    '''Parse an old-compatible GC CSV archive member name.

    Args:
        member_name: Archive member name or basename.

    Returns:
        Mapping with ``compound_id``, ``ri_type``, ``column_type``, and
        ``temp_regime``.

    Raises:
        ValueError: If the member name does not follow the expected four-part
            underscore-separated convention.

    '''
    basename = Path(member_name).name
    if not basename.lower().endswith('.csv'):
        raise ValueError(f'not a CSV member: {member_name}')

    stem = basename[:-4]
    parts = stem.split('_', 3)
    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError(f'bad GC member name: {member_name}')

    return {
        'compound_id': parts[0],
        'ri_type': parts[1],
        'column_type': parts[2],
        'temp_regime': parts[3],
    }


def gc_archive_members_by_compound(
    path_zip: str | Path,
    require_nonempty: bool = True,
) -> dict[str, dict[str, str]]:
    '''Group existing GC CSV ZIP members by compound ID.

    The returned nested mapping has this form::

        {compound_id: {canonical_basename: actual_archive_member}}

    This lets users reuse old loose GC CSV files after placing them into a ZIP,
    including archives where files were stored under a top-level directory.

    Args:
        path_zip: Path to the ZIP archive.
        require_nonempty: If true, zero-size members are ignored.

    Returns:
        Mapping from compound ID to existing GC archive members.

    '''
    grouped: dict[str, dict[str, str]] = {}
    for basename, member in archive_members_by_basename(
        path_zip, require_nonempty=require_nonempty
    ).items():
        try:
            info = parse_legacy_gc_member_name(basename)
        except ValueError:
            continue

        canonical = legacy_gc_member_name(
            info['compound_id'],
            info['ri_type'],
            info['column_type'],
            info['temp_regime'],
        )
        grouped.setdefault(info['compound_id'], {})[canonical] = member

    return grouped


def format_archive_members(members: Iterable[str]) -> str:
    '''Format archive member names for a manifest cell.

    Args:
        members: Archive member names.

    Returns:
        Semicolon-separated member list.

    '''
    return ';'.join(str(member) for member in members)


def parse_archive_members(value: Any) -> list[str]:
    '''Parse a manifest archive-member cell.

    Args:
        value: Semicolon-separated archive member list.

    Returns:
        List of non-empty archive member names.

    '''
    if value is None:
        return []

    return [member.strip() for member in str(value).split(';') if member.strip()]


def archive_members_present(
    archive_sizes: Mapping[str, int],
    members: Sequence[str],
    require_nonempty: bool = True,
) -> bool:
    '''Check whether manifest-listed members exist in an archive.

    Args:
        archive_sizes: Mapping returned by ``zip_member_sizes``.
        members: Archive members listed in a manifest row.
        require_nonempty: If true, members with zero size are treated as
            missing/incomplete.

    Returns:
        True if all listed members are present and, when requested, non-empty.
        Empty member lists are never considered complete.

    '''
    if not members:
        return False

    for member in members:
        if member not in archive_sizes:
            return False
        if require_nonempty and archive_sizes[member] <= 0:
            return False

    return True


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



def latest_manifest_rows(
    path_manifest: str | Path,
    data_type: str | None = None,
) -> dict[str, dict[str, str]]:
    '''Return the latest manifest row for each compound ID.

    Args:
        path_manifest: Path to the manifest CSV file.
        data_type: Optional data-type filter.

    Returns:
        Mapping from compound ID to the latest matching manifest row. Later rows
        override earlier rows because append-only manifests record the most recent
        state last.

    '''
    latest: dict[str, dict[str, str]] = {}
    for row in read_manifest_rows(path_manifest):
        if data_type is not None and row.get('data_type') != data_type:
            continue

        compound_id = row.get('compound_id')
        if compound_id:
            latest[compound_id] = row

    return latest


def completed_ids_for_download(
    path_manifest: str | Path,
    data_type: str,
    path_archive: str | Path,
    archive_state: Mapping[str, Mapping[str, str]],
    require_nonempty: bool = True,
) -> set[str]:
    '''Return compound IDs that can be skipped by a download workflow.

    The function combines the append-only manifest with the current archive
    contents while avoiding stale-state mistakes:

    - if the latest manifest row for an ID is a valid ``done`` row whose listed
      archive members are present, the ID is complete;
    - if no manifest row exists for an ID, non-empty archive members can be used
      as legacy/local resume state;
    - if the latest manifest row is ``error``, ``no_data``, or an invalid
      ``done`` row, archive-only state is not trusted and the ID is rechecked.

    Args:
        path_manifest: Path to the manifest CSV file.
        data_type: Manifest data type for the current workflow.
        path_archive: ZIP archive path used to validate manifest-listed members.
        archive_state: Existing archive members grouped by compound ID.
        require_nonempty: If true, zero-size archive members are treated as
            incomplete.

    Returns:
        Set of compound IDs that can be skipped without contacting the source.

    '''
    try:
        archive_sizes = zip_member_sizes(path_archive)
    except zipfile.BadZipFile:
        return set()

    latest = latest_manifest_rows(path_manifest, data_type=data_type)
    completed: set[str] = set()

    for compound_id, row in latest.items():
        if row.get('status') != 'done':
            continue

        members = parse_archive_members(row.get('archive_members'))
        if archive_members_present(
            archive_sizes,
            members,
            require_nonempty=require_nonempty,
        ):
            completed.add(compound_id)

    # Existing non-empty archive members are useful for reusing legacy/local raw
    # archives without manifests. They are used only when the manifest has no
    # state for the compound; an explicit latest error/no_data/invalid-done row
    # should trigger a repair attempt instead of silent skipping.
    for compound_id in archive_state:
        if compound_id not in latest:
            completed.add(compound_id)

    return completed


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
