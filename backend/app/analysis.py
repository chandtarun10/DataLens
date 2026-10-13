import csv
import io
import re
import warnings
from datetime import date, datetime

import numpy as np
import pandas as pd


# =========================================================
# FILE LOADING
# =========================================================

def csv_source_rows(data: bytes, encoding: str, record_count: int):
    """
    Real row number (as shown by Excel / a spreadsheet viewer) of every
    data record of a CSV file: the header is the first non-blank row and
    blank lines still count as rows, even though pandas skips them.

    Returns None when the count does not match the parsed dataframe, so
    the caller can fall back to the simple "position + header" rule.
    """
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        return None

    if text.startswith('\ufeff'):
        text = text[1:]

    rows = []

    for line_number, fields in enumerate(
        csv.reader(io.StringIO(text, newline='')),
        start=1
    ):
        if fields:
            rows.append(line_number)

    # First non-blank row is the header; the rest are data records.
    rows = rows[1:]

    if len(rows) != record_count:
        return None

    # A compact array: pandas deep-copies df.attrs on many operations, which
    # is very slow for a Python list with one entry per row.
    return np.asarray(rows, dtype=np.int64)


def detect_excel_header_row(data: bytes) -> int:
    preview = pd.read_excel(
        io.BytesIO(data),
        header=None,
        nrows=30
    )

    if preview.empty:
        return 0

    best_row = 0
    best_score = float("-inf")

    for i in range(len(preview)):
        row = preview.iloc[i]
        non_empty = row.dropna()

        if len(non_empty) == 0:
            continue

        filled_ratio = len(non_empty) / len(row)
        uniqueness = (
            non_empty.astype(str).nunique() / len(non_empty)
        )

        next_rows = preview.iloc[i + 1:min(i + 6, len(preview))]

        if next_rows.empty:
            data_support = 0
        else:
            data_support = next_rows.notna().mean(axis=1).mean()

        # Header cells are usually text, unlike many data rows.
        text_ratio = sum(
            isinstance(value, str)
            for value in non_empty.tolist()
        ) / len(non_empty)

        score = (
            2 * filled_ratio
            + uniqueness
            + data_support
            + 1.5 * text_ratio
        )

        if score > best_score:
            best_score = score
            best_row = i

    return best_row


def load_dataframe(data: bytes, ext: str) -> pd.DataFrame:
    bio = io.BytesIO(data)

    if ext == '.csv':
        encoding = 'utf-8'

        try:
            df = pd.read_csv(bio)
        except UnicodeDecodeError:
            bio.seek(0)
            encoding = 'latin-1'
            df = pd.read_csv(bio, encoding='latin-1')

        source_rows = csv_source_rows(
            data,
            encoding,
            len(df)
        )

        if source_rows is not None:
            df.attrs['source_rows'] = source_rows

        return df

    header_row = detect_excel_header_row(data)
    df = pd.read_excel(io.BytesIO(data), header=header_row)

    # Remove columns that are entirely empty.
    df = df.dropna(axis=1, how='all')

    return df


# =========================================================
# BASIC VALUE HELPERS
# =========================================================

def clean_scalar(v):
    # pd.isna() can return an array-like result for unusual cell values.
    # Normal CSV/Excel scalar values remain fully supported.
    try:
        missing = pd.isna(v)
        if isinstance(missing, (bool, np.bool_)) and missing:
            return None
    except Exception:
        pass

    if isinstance(v, np.integer):
        return int(v)

    if isinstance(v, np.floating):
        return None if not np.isfinite(v) else float(v)

    if isinstance(v, pd.Timestamp):
        return v.isoformat()

    return v.item() if hasattr(v, 'item') else v


def pretty(v):
    v = clean_scalar(v)

    if v is None:
        return ''

    if isinstance(v, float):
        return round(v, 4)

    return v


# =========================================================
# MISSING VALUE NORMALIZATION
# =========================================================

COMMON_MISSING_STRINGS = {
    '',
    'na',
    'n/a',
    'nan',
    'null',
    'none',
    'nil',
    'missing',
    'not available',
    'not_applicable',
    'not applicable',
}


def normalize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert common textual missing-value representations into NaN.

    We intentionally do NOT treat '-' or '?' as universally missing
    because those symbols can be legitimate values in real datasets.
    """
    df = df.copy()

    for column in df.columns:
        series = df[column]

        if (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
        ):
            cleaned = series.astype('string').str.strip()

            missing_mask = cleaned.str.lower().isin(
                COMMON_MISSING_STRINGS
            )

            df.loc[missing_mask.fillna(False), column] = np.nan

    return df


# =========================================================
# NUMERIC / DATE PARSING HELPERS
# =========================================================
#
# These helpers let the analyzer look at the VALUES of a column
# instead of trusting the pandas dtype. A column that pandas stores
# as text ("object") because of a few dirty cells is still understood
# as numeric/date when most of its valid values are numeric/date.

_CURRENCY_RE = re.compile(r'[\$€£¥₹]')

# 60,000 / 1,250,000.50  (comma used as a thousands separator)
_THOUSANDS_RE = re.compile(r'^[-+]?\d{1,3}(,\d{3})+(\.\d+)?$')

_NUMBER_WORDS = {
    'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
    'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen',
    'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen',
    'nineteen', 'twenty', 'thirty', 'forty', 'fifty', 'sixty',
    'seventy', 'eighty', 'ninety', 'hundred', 'thousand', 'lakh',
    'million', 'crore', 'billion', 'and'
}

# Text that is clearly a "placeholder for a number" without being one
# of the common missing-value strings handled by normalize_missing_values.
_NUMERIC_PLACEHOLDERS = {
    'unknown', 'unk', 'tbd', 'tba', 'undefined', 'unspecified',
    'not known', '?', '-', '--'
}

_MONTH_NAME_RE = re.compile(
    r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b',
    re.IGNORECASE
)

# 2024-01-01 / 01/15/2024 / 15.01.2024 / 2024-01-01 10:30:00
_NUMERIC_DATE_RE = re.compile(
    r'^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}([ T,].*)?$'
)


def is_text_dtype(series):
    return (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
    )


def parse_numeric_series(series):
    """
    Interpret a column as numbers without throwing the column away
    because of a few dirty cells.

    Returns (values, formatted_mask, invalid_mask):

        values          float Series aligned with `series`
                        (NaN for missing AND for non-numeric cells)
        formatted_mask  True where the cell is numeric but needed cleaning
                        ("60,000", "$1,200", "12%")
        invalid_mask    True where the cell is present but not a number
                        ("Twenty Seven", "unknown")
    """
    present = series.notna()

    values = pd.Series(
        np.nan,
        index=series.index,
        dtype='float64'
    )

    formatted = pd.Series(False, index=series.index)

    if not present.any():
        return values, formatted, pd.Series(False, index=series.index)

    if pd.api.types.is_bool_dtype(series):
        invalid = present.copy()
        return values, formatted, invalid

    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors='coerce').astype('float64')
        numeric = numeric.where(np.isfinite(numeric))
        invalid = present & numeric.isna()
        return numeric, formatted, invalid

    # Text / mixed-object column: work on the string form of each cell.
    text = series[present].astype(str).str.strip()

    direct = pd.to_numeric(text, errors='coerce')
    direct = direct.where(np.isfinite(direct))

    values.loc[direct.index] = direct

    leftover = text[direct.isna()]

    if len(leftover):
        cleaned = (
            leftover
            .str.replace(_CURRENCY_RE, '', regex=True)
            .str.strip()
            .str.replace(r'^\((.*)\)$', r'-\1', regex=True)
            .str.replace(r'\s*%$', '', regex=True)
            .str.strip()
        )

        thousands = cleaned.str.match(_THOUSANDS_RE)

        cleaned = cleaned.where(
            ~thousands,
            cleaned.str.replace(',', '', regex=False)
        )

        recovered = pd.to_numeric(cleaned, errors='coerce')
        recovered = recovered.where(np.isfinite(recovered))
        recovered = recovered[recovered.notna()]

        if len(recovered):
            values.loc[recovered.index] = recovered
            formatted.loc[recovered.index] = True

    invalid = present & values.isna()

    return values, formatted, invalid


def numeric_values(series):
    """Valid numeric values of a column (dirty cells are ignored)."""
    values, _, _ = parse_numeric_series(series)

    return values.dropna()


def looks_like_numeric_junk(value):
    """
    True for text that is obviously a stand-in for a number
    ("Twenty Seven", "unknown", "TBD").
    """
    token = str(value).strip().lower()

    if token in _NUMERIC_PLACEHOLDERS:
        return True

    words = [w for w in re.split(r'[\s\-]+', token) if w]

    return bool(words) and all(w in _NUMBER_WORDS for w in words)


def numeric_profile(series):
    non_null = int(series.notna().sum())

    values, formatted, invalid = parse_numeric_series(series)

    valid = int(values.notna().sum())

    invalid_cells = series[invalid]

    junk = (
        int(invalid_cells.map(looks_like_numeric_junk).sum())
        if len(invalid_cells)
        else 0
    )

    return {
        'non_null': non_null,
        'valid': valid,
        'formatted': int(formatted.sum()),
        'invalid': int(invalid.sum()),
        'junk': junk,
        'ratio': (valid / non_null) if non_null else 0.0
    }


def is_numeric_measure_profile(profile):
    """
    A column is a numeric measure when most of its values are numbers.

    - >= 80% parseable: numeric.
    - 50-80% parseable: numeric only if nearly all of the remaining
      cells are number-words / placeholders ("Twenty Seven", "unknown"),
      so genuine mixed categorical columns are not captured.
    """
    non_null = profile['non_null']

    if non_null == 0 or profile['valid'] == 0:
        return False

    if profile['ratio'] >= 0.80:
        return True

    return (
        profile['ratio'] >= 0.50
        and (profile['valid'] + profile['junk']) / non_null >= 0.90
    )


def parse_date_series(series):
    """
    Parse a column of dates (real datetimes or text) value by value.

    Returns (parsed, candidates):
        parsed      datetime64 Series, NaT where not a valid date
        candidates  bool Series: cells that structurally look like dates

    Plain numbers ("25", "2024") and free text are never treated as dates.
    """
    present = series.notna()

    parsed = pd.Series(
        pd.NaT,
        index=series.index,
        dtype='datetime64[ns]'
    )

    if not present.any():
        return parsed, pd.Series(False, index=series.index)

    if pd.api.types.is_datetime64_any_dtype(series):
        converted = series
        try:
            if getattr(converted.dt, 'tz', None) is not None:
                converted = converted.dt.tz_localize(None)
        except Exception:
            pass
        return converted, present

    candidates = pd.Series(False, index=series.index)

    # Real date/datetime objects (typical for Excel cells).
    object_mask = present & series.map(
        lambda v: isinstance(v, (datetime, date))
    )

    if object_mask.any():
        try:
            objects = pd.to_datetime(
                series[object_mask],
                errors='coerce'
            )
            parsed.loc[objects.index] = objects
        except Exception:
            pass

        candidates |= object_mask

    # Text cells.
    text_mask = present & ~object_mask

    if text_mask.any():
        text = series[text_mask].astype(str).str.strip()

        looks_like_date = (
            text.str.match(_NUMERIC_DATE_RE)
            | (
                text.str.contains(_MONTH_NAME_RE)
                & text.str.contains(r'\d', regex=True)
            )
        )

        candidate_text = text[looks_like_date]

        candidates.loc[candidate_text.index] = True

        if len(candidate_text):
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')

                day_first = infer_day_first(candidate_text)

                try:
                    converted = pd.to_datetime(
                        candidate_text,
                        errors='coerce',
                        format='mixed',
                        dayfirst=day_first
                    )
                except Exception:
                    try:
                        converted = pd.to_datetime(
                            candidate_text,
                            errors='coerce',
                            utc=True
                        ).dt.tz_localize(None)
                    except Exception:
                        converted = pd.Series(
                            pd.NaT,
                            index=candidate_text.index
                        )

            try:
                if getattr(converted.dt, 'tz', None) is not None:
                    converted = converted.dt.tz_localize(None)
            except Exception:
                pass

            parsed.loc[converted.index] = converted

    return parsed, candidates


def infer_day_first(candidate_text):
    """
    Decide from the DATA whether numeric dates such as 03/04/2024 are
    day-first (3 April) or month-first (March 4).

    Month-first is the default. A column is read as day-first only when it
    contains a date whose first part cannot be a month (e.g. 15/04/2024)
    and none whose second part cannot be a month (e.g. 04/15/2024).
    Without this, every ambiguous day-first date silently lands in the
    wrong month and distorts the monthly chart and the date range.
    """
    parts = candidate_text.str.extract(
        r'^\s*(\d{1,2})[-/.](\d{1,2})[-/.]\d{2,4}\b'
    )

    first = pd.to_numeric(parts[0], errors='coerce')
    second = pd.to_numeric(parts[1], errors='coerce')

    def valid_dates(mask, day_first):
        evidence = candidate_text[mask.fillna(False)]

        if evidence.empty:
            return 0

        with warnings.catch_warnings():
            warnings.simplefilter('ignore')

            try:
                parsed = pd.to_datetime(
                    evidence,
                    errors='coerce',
                    format='mixed',
                    dayfirst=day_first
                )
            except Exception:
                return 0

        return int(parsed.notna().sum())

    # Evidence only counts when the date really is valid that way
    # (31/04/2024 is invalid either way and proves nothing).
    day_first_evidence = valid_dates(first > 12, True)
    month_first_evidence = valid_dates(second > 12, False)

    return bool(day_first_evidence > 0 and month_first_evidence == 0)


def date_format_signature(value):
    """
    Shape of a date string, e.g. '2024-01-01' -> 'Y-d-d',
    'March 5 2024' -> 'A d Y'. Used to spot mixed date formats.
    """
    text = str(value).strip()

    text = re.sub(r'[A-Za-z]+', 'A', text)

    return re.sub(
        r'\d+',
        lambda m: 'Y' if len(m.group()) >= 4 else 'd',
        text
    )


# =========================================================
# SOURCE ROW NUMBERS
# =========================================================

# The uploaded file has ONE header row, so the first data record is
# physically on row 2 of the CSV / Excel sheet.
HEADER_ROWS = 1


def source_row_numbers(df: pd.DataFrame):
    """
    Return 1-based data-record numbers.
    The first data record is row 1, regardless of file header.
    """
    return np.arange(1, len(df) + 1, dtype=int)


# =========================================================
# ISSUE RECORDS
# =========================================================

def build_issue_records(
    df: pd.DataFrame,
    mask,
    include_missing_columns=False
):
    records = []

    selected_positions = np.flatnonzero(
        mask.to_numpy()
    )

    source_rows = source_row_numbers(df)

    for position in selected_positions:

        row = df.iloc[position]

        record = {
            'row_number': int(source_rows[position]),
            'values': {
                str(column): clean_scalar(value)
                for column, value in row.items()
            }
        }

        if include_missing_columns:
            record['missing_columns'] = [
                str(column)
                for column, value in row.items()
                if pd.isna(value)
            ]

        records.append(record)

    return records


# =========================================================
# DUPLICATE / TEXT QUALITY HELPERS
# =========================================================

def normalized_text_value(value):
    """Normalize text only for comparison; never modify the source value."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return re.sub(r'\s+', ' ', str(value).strip()).casefold()


def _stable_key_value(value):
    value = clean_scalar(value)
    if value is None:
        return ('__MISSING__',)
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


# Duplicate RECORD detection. Two different concepts are kept apart:
#   exact duplicates ........ every column is identical
#   identifier-excluded ..... all non-identifier columns match while identifier
#                             columns (IDs, codes) differ
# Duplicate IDENTIFIER VALUES are a third, separate check
# (detect_identifier_duplicates).

MIN_KEY_COLUMNS = 3
MAX_EXTRA_DUPLICATE_SHARE = 0.25
_MISSING_KEY = ('__MISSING__',)


def duplicate_comparison_columns(df, identifier_columns=None):
    """
    Columns compared when looking for duplicate records ignoring identifiers.

    Rule: columns classified as identifiers are ignored, but only if at
    least MIN_KEY_COLUMNS descriptive columns remain. Otherwise there is
    too little left to say two records describe the same thing, so every
    column is compared (exact comparison).
    """
    ids = {str(x) for x in (identifier_columns or [])}

    columns = [c for c in df.columns if str(c) not in ids]

    if len(columns) < MIN_KEY_COLUMNS or len(columns) == len(df.columns):
        return list(df.columns)

    return columns


def build_duplicate_analysis(df, identifier_columns=None):
    """
    One pass that yields every duplicate figure the dashboard, the quality
    summary and the reports use, so they can never disagree.
    """
    all_columns = list(df.columns)
    key_columns = duplicate_comparison_columns(df, identifier_columns)
    ignores_identifiers = len(key_columns) < len(all_columns)
    ignored = [str(c) for c in all_columns if c not in key_columns]
    key_index = [i for i, c in enumerate(all_columns) if c in key_columns]
    ignored_index = [i for i, c in enumerate(all_columns) if c not in key_columns]
    source_rows = source_row_numbers(df)
    total_rows = len(df)

    column_values = [
        [_stable_key_value(v) for v in df[c].tolist()]
        for c in all_columns
    ]

    full_keys = list(zip(*column_values)) if column_values else []

    def informative(key):
        # A record whose compared columns are (almost) all empty says nothing.
        return sum(1 for v in key if v != _MISSING_KEY) >= 2

    def groups_from(keys, need_information):
        buckets = {}

        for position, key in enumerate(keys):
            buckets.setdefault(key, []).append(position)

        return [
            positions
            for key, positions in buckets.items()
            if len(positions) > 1
            and (not need_information or informative(key))
        ]

    exact_groups = groups_from(full_keys, False)
    exact_rows = sum(len(p) - 1 for p in exact_groups)

    suppressed = False
    final_groups = exact_groups

    if ignores_identifiers:
        semantic_keys = [
            tuple(key[i] for i in key_index)
            for key in full_keys
        ]

        semantic_groups = groups_from(semantic_keys, True)

        covered = {p for group in semantic_groups for p in group}

        # An exact duplicate is always kept, even if its key is too empty
        # to count as an informative semantic match.
        semantic_groups += [
            g for g in exact_groups if g[0] not in covered
        ]

        extra_rows = (
            sum(len(p) - 1 for p in semantic_groups) - exact_rows
        )

        # If ignoring identifiers makes a large share of the dataset
        # "duplicate", the remaining columns are too generic to indicate
        # real duplication (e.g. an ID plus two categories). Fall back to
        # exact duplicates only instead of reporting false groups.
        if (
            total_rows >= 20 
            and extra_rows / total_rows > MAX_EXTRA_DUPLICATE_SHARE
        ):
            suppressed = True
        else:
            final_groups = semantic_groups

    final_groups = sorted(final_groups, key=lambda g: g[0])

    groups = []
    repeat_positions = []

    for group_id, positions in enumerate(final_groups, start=1):
        # Every record of a group is classified exactly once, so exact and
        # identifier-only duplicates can never be counted twice:
        #   original ............ the first row
        #   exact_duplicate ..... every column equals an earlier row of the group
        #   identifier_duplicate  non-identifier columns match; an identifier differs
        seen_full = {full_keys[positions[0]]}
        duplicate_types = ['original']

        for position in positions[1:]:
            if full_keys[position] in seen_full:
                duplicate_types.append('exact_duplicate')
            else:
                duplicate_types.append('identifier_duplicate')
                seen_full.add(full_keys[position])

        rows = []

        for position, duplicate_type in zip(positions, duplicate_types):
            row = df.iloc[position]

            rows.append({
                'row_number': int(source_rows[position]),
                'duplicate_type': duplicate_type,
                'values': {
                    str(column): clean_scalar(value)
                    for column, value in row.items()
                }
            })

        exact_count = duplicate_types.count('exact_duplicate')
        identifier_count = duplicate_types.count('identifier_duplicate')

        differing = [
            all_columns[j]
            for j in ignored_index
            if len({full_keys[p][j] for p in positions}) > 1
        ]

        repeat_positions.extend(positions[1:])

        groups.append({
            'group_id': group_id,
            'count': int(len(positions)),
            'duplicate_count': int(len(positions) - 1),
            'exact_duplicate_count': int(exact_count),
            'identifier_only_duplicate_count': int(identifier_count),
            'row_numbers': [int(source_rows[p]) for p in positions],
            'original_row': int(source_rows[positions[0]]),
            'match_type': (
                'exact' if identifier_count == 0 else 'identifier_excluded'
            ),
            'differing_identifier_columns': [str(c) for c in differing],
            'rows': rows
        })

    # All totals come from the groups themselves, so the summary can never
    # disagree with the detailed duplicate-group view.
    exact_total = sum(g['exact_duplicate_count'] for g in groups)
    identifier_total = sum(g['identifier_only_duplicate_count'] for g in groups)

    return {
        'groups': groups,
        # Exact duplicates: every column identical to an earlier record.
        'exact_duplicate_rows': int(exact_total),
        # Groups that contain at least one exact duplicate.
        'exact_duplicate_groups': int(
            sum(1 for g in groups if g['exact_duplicate_count'] > 0)
        ),
        # ADDITIONAL duplicates found only by ignoring identifier columns
        # (never includes the exact duplicates).
        'additional_duplicate_rows_ignoring_identifiers': int(identifier_total),
        'identifier_only_duplicate_groups': int(
            sum(1 for g in groups if g['identifier_only_duplicate_count'] > 0)
        ),
        # All repeated records = exact + additional.
        'duplicate_rows_ignoring_identifiers': int(exact_total + identifier_total),
        'duplicate_groups_total': int(len(groups)),
        'key_columns': [str(c) for c in key_columns],
        'ignored_identifier_columns': (
            ignored if ignores_identifiers and not suppressed else []
        ),
        'identifier_comparison_suppressed': bool(suppressed),
        'repeat_positions': sorted(repeat_positions)
    }


def build_duplicate_mask(df, identifier_columns=None):
    """Rows that repeat an earlier record (kept for compatibility)."""
    analysis = build_duplicate_analysis(df, identifier_columns)

    mask = pd.Series(False, index=df.index)

    if analysis['repeat_positions']:
        mask.iloc[analysis['repeat_positions']] = True

    return mask


def build_duplicate_groups(df, identifier_columns=None):
    return build_duplicate_analysis(df, identifier_columns)['groups']


EXPECTED_UNIQUE_RATIO = 0.80


def detect_identifier_duplicates(df, identifier_columns):
    """
    Repeated values inside identifier columns.

    Only columns that are expected to be unique (almost every value is
    distinct) are checked: a repeating Customer_ID in an orders table is
    normal. Missing identifiers are never counted as repeats.
    """
    source_rows = source_row_numbers(df)

    result = []

    for name in identifier_columns:
        series = df[name]

        present = series.notna().to_numpy()

        if present.sum() < 2:
            continue

        unique_ratio = float(series.dropna().nunique() / present.sum())

        if unique_ratio < EXPECTED_UNIQUE_RATIO:
            continue

        repeated = (series.notna() & series.duplicated(keep=False)).to_numpy()

        if not repeated.any():
            continue

        grouped = {}

        for position in np.flatnonzero(repeated):
            value = series.iloc[position]

            key = _stable_key_value(value)

            grouped.setdefault(
                key,
                {'value': clean_scalar(value), 'positions': []}
            )

            grouped[key]['positions'].append(int(position))

        values = [
            {
                'value': item['value'],
                'count': int(len(item['positions'])),
                'row_numbers': [
                    int(source_rows[p]) for p in item['positions']
                ]
            }
            for item in grouped.values()
        ]

        values.sort(key=lambda v: (-v['count'], v['row_numbers'][0]))

        result.append({
            'column': str(name),
            'duplicate_values': values,
            'duplicate_occurrences': int(repeated.sum()),
            'unique_ratio': round(unique_ratio, 4)
        })

    return result


def _short_rows(row_numbers, limit=6):
    shown = ', '.join(str(r) for r in row_numbers[:limit])

    return shown + (', ...' if len(row_numbers) > limit else '')


def _rows_text(row_numbers, limit=6):
    label = 'row' if len(row_numbers) == 1 else 'rows'

    return f'{label} {_short_rows(row_numbers, limit)}'


def _number_text(value):
    value = float(value)

    return (
        f'{int(value):,}'
        if value.is_integer()
        else f'{value:,.2f}'
    )


def _numeric_identifier_anomalies(series, column_name, source_rows):
    """
    Potential anomalies in numeric identifiers: a jump in a sequence that is
    otherwise regular, and values whose length differs from the rest.
    No mean/median of the identifier is ever computed.
    """
    values, _, _ = parse_numeric_series(series)

    valid = values.dropna()

    result = []

    if len(valid) < 5:
        return result

    def rows_of(mask):
        positions = np.flatnonzero(mask.to_numpy())

        return [int(source_rows[p]) for p in positions]

    unique = np.sort(valid.unique())

    differences = np.diff(unique)

    positive = differences[differences > 0]

    if len(positive) >= 3:
        steps, step_counts = np.unique(positive, return_counts=True)

        dominant_step = float(steps[np.argmax(step_counts)])

        regular_share = float(step_counts.max() / len(positive))

        # A gap is only suspicious when the identifiers normally advance
        # in a regular way; random-looking IDs have no expected step.
        if regular_share >= 0.60 and dominant_step > 0:
            for low, high, gap in zip(unique[:-1], unique[1:], differences):
                if gap <= dominant_step * 10:
                    continue

                rows = rows_of(values == high)

                result.append({
                    'type': 'numeric_gap',
                    'column': str(column_name),
                    'value_before': clean_scalar(low),
                    'value_after': clean_scalar(high),
                    'gap': clean_scalar(gap),
                    'typical_step': clean_scalar(dominant_step),
                    'examples': [clean_scalar(high)],
                    'row_numbers': rows,
                    'message': (
                        f'Potential anomaly in {column_name}: the identifier '
                        f'sequence normally advances by '
                        f'{_number_text(dominant_step)} but jumps from '
                        f'{_number_text(low)} to {_number_text(high)} '
                        f'({_rows_text(rows)}).'
                    )
                })

    integer_like = valid[valid.map(lambda v: float(v).is_integer())]

    if len(integer_like) >= 5:
        widths = integer_like.map(lambda v: len(str(abs(int(v)))))

        if widths.nunique() > 1:
            counts = widths.value_counts()

            dominant = int(counts.index[0])

            minority = integer_like[widths != dominant]

            # Natural growth of a counter (1..500 has 1-, 2- and 3-digit
            # values) is not an anomaly: skip when every shorter value sits
            # right below the dominant-length values with no real gap.
            dominant_values = integer_like[widths == dominant]

            typical_step = (
                float(np.median(positive)) if len(positive) else 1.0
            )

            natural_growth = bool(
                len(minority)
                and minority.max() < dominant_values.min()
                and dominant_values.min() - minority.max()
                <= 10 * max(typical_step, 1.0)
            )

            if natural_growth:
                minority = minority.iloc[0:0]

            minority_ratio = len(minority) / len(widths)

            width_difference = max(
                abs(int(w) - dominant) for w in widths.unique()
            )

            if len(minority) and (
                width_difference >= 2 or minority_ratio <= 0.05
            ):
                rows = [
                    int(source_rows[series.index.get_loc(i)])
                    for i in minority.index
                ]

                shown = _examples(minority.map(_number_text), 3)

                result.append({
                    'type': 'digit_width_inconsistency',
                    'column': str(column_name),
                    'expected_digits': dominant,
                    'row_numbers': rows,
                    'examples': _examples(minority.map(_number_text)),
                    'message': (
                        f'Potential anomaly in {column_name}: '
                        f'{len(minority)} identifier(s) have a different '
                        f'length than the dominant {dominant}-digit format, '
                        f'e.g. {", ".join(shown)} '
                        f'({_rows_text(rows)}).'
                    )
                })

    return result


def _code_prefix(value):
    match = re.match(r'^([A-Za-z]+)[-_]?', str(value).strip())

    return match.group(1).casefold() if match else ''


def _digit_run_lengths(value):
    return tuple(len(run) for run in re.findall(r'\d+', str(value)))


def detect_identifier_anomalies(df, identifier_columns):
    """Potential anomalies in identifier formats (generic, explainable)."""
    source_rows = source_row_numbers(df)

    result = []

    for name in identifier_columns:
        series = df[name]

        result.extend(
            _numeric_identifier_anomalies(series, str(name), source_rows)
        )

        non_null = series.dropna()

        if len(non_null) < 8 or not is_text_dtype(series):
            continue

        texts = non_null.astype(str).str.strip()

        # Prefix / digit-length checks only make sense for code-like
        # identifiers (EMP-001, ORD1002); UUIDs and e-mails are skipped.
        if texts.str.match(_CODE_RE).mean() < 0.80:
            continue

        def rows_of_index(index):
            return [
                int(source_rows[series.index.get_loc(i)]) for i in index
            ]

        prefixes = texts.map(_code_prefix)

        flagged_by_prefix = set()

        usable = prefixes[prefixes != '']

        if len(usable) >= 8 and usable.nunique() > 1:
            counts = usable.value_counts()

            dominant = counts.index[0]

            minority = texts[usable.reindex(texts.index).fillna('') != dominant]

            if (
                len(dominant) >= 2
                and len(minority)
                and len(minority) / len(texts) <= 0.35
            ):
                flagged_by_prefix = set(minority.index)

                rows = rows_of_index(minority.index)

                result.append({
                    'type': 'prefix_inconsistency',
                    'column': str(name),
                    'expected_prefix': dominant,
                    'row_numbers': rows,
                    'examples': _examples(minority),
                    'message': (
                        f"Potential anomaly in {name}: {len(minority)} "
                        f"identifier(s) use a different prefix than the "
                        f"dominant '{dominant}', e.g. "
                        f"{', '.join(_examples(minority, 3))} "
                        f"({_rows_text(rows)})."
                    )
                })

        shapes = texts.map(_digit_run_lengths)

        shape_counts = shapes.value_counts()

        if len(shape_counts) > 1:
            dominant_shape = shape_counts.index[0]

            minority = texts[
                (shapes != dominant_shape)
                & ~texts.index.isin(flagged_by_prefix)
            ]

            if (
                len(minority)
                and shape_counts.iloc[0] / len(texts) >= 0.60
            ):
                rows = rows_of_index(minority.index)

                result.append({
                    'type': 'format_inconsistency',
                    'column': str(name),
                    'expected_digits': list(dominant_shape),
                    'row_numbers': rows,
                    'examples': _examples(minority),
                    'message': (
                        f'Potential anomaly in {name}: {len(minority)} '
                        f'identifier(s) have a different number of digits '
                        f'than the dominant format, e.g. '
                        f'{", ".join(_examples(minority, 3))} '
                        f'({_rows_text(rows)}).'
                    )
                })

    return result


def detect_text_inconsistencies(df, profiles):
    """Find categorical/text values differing only by case or whitespace."""
    source_rows = source_row_numbers(df)
    result = []
    for profile in profiles:
        name = profile['name']
        if profile['role'] != 'category':
            continue
        series = df[name]
        if not is_text_dtype(series):
            continue
        non_null = series.dropna()
        if len(non_null) < 2:
            continue
        normalized = non_null.map(normalized_text_value)
        groups = {}
        for idx, norm in normalized.items():
            groups.setdefault(norm, []).append(idx)
        variants = []
        for norm, indexes in groups.items():
            originals = []
            for idx in indexes:
                value = str(series.loc[idx])
                if value not in originals:
                    originals.append(value)
            if len(originals) > 1:
                variants.append({
                    'normalized_value': norm,
                    'variants': originals,
                    'count': int(len(indexes)),
                    'row_numbers': [int(source_rows[df.index.get_loc(i)]) for i in indexes]
                })
        if variants:
            shown = '; '.join(
                ' / '.join(repr(v) for v in group['variants'][:4])
                for group in variants[:3]
            )
            result.append({
                'column': str(name),
                'variant_groups': variants,
                'variant_count': int(len(variants)),
                'message': (
                    f'{name} contains values that differ only by case or '
                    f'whitespace and were treated as separate categories '
                    f'in the original data: {shown}.'
                )
            })
    return result


# =========================================================
# PLACEHOLDER-LIKE VALUES
# =========================================================
#
# Actual missing cells are already handled by normalize_missing_values()
# (blank, NA, N/A, null, None, nil, missing, "not available" ...).
# The values below are different: they are present in the data but may
# stand in for "unknown". They are reported separately, are NOT counted
# as missing cells, and the data is never modified, because whether
# "unknown" is a real category depends on the column.

PLACEHOLDER_VALUES = {
    'unknown', 'unk', 'unspecified', 'not specified', 'not provided',
    'not known', 'unavailable', 'no data', 'no info', 'tbd', 'tba',
    'to be determined', 'undefined', 'n.a.', 'n.a', '?', '??', '-',
    '--', '---'
}


def detect_placeholder_values(df, profiles):
    source_rows = source_row_numbers(df)

    result = []

    for profile in profiles:
        name = profile['name']

        series = df[name]

        if not is_text_dtype(series) or profile['non_null'] == 0:
            continue

        text = series.dropna().astype(str).str.strip()

        hits = text[text.str.casefold().isin(PLACEHOLDER_VALUES)]

        if hits.empty:
            continue

        counts = hits.value_counts()

        positions = [
            series.index.get_loc(i) for i in hits.index
        ]

        rows = [int(source_rows[p]) for p in positions]

        examples = ', '.join(
            f"'{value}' x{int(count)}"
            for value, count in counts.head(5).items()
        )

        result.append({
            'column': str(name),
            'count': int(len(hits)),
            'percent_of_column': round(
                float(len(hits) / profile['non_null'] * 100), 2
            ),
            'values': [
                {'value': str(v), 'count': int(c)}
                for v, c in counts.items()
            ],
            'row_numbers': rows,
            'message': (
                f'{name}: {len(hits)} placeholder-like value(s) '
                f'({examples}) ({_rows_text(rows)}); not counted '
                f'as missing cells.'
            )
        })

    return result


# =========================================================
# EXTREME SKEW (histogram readability)
# =========================================================

def describe_extreme_skew(values):
    """
    Detect values so far outside the typical range that they squeeze the
    rest of a histogram into one or two bars. Nothing is removed or
    changed; the result is only an explanatory note.
    """
    s = pd.Series(values, dtype='float64').dropna()

    if len(s) < 8:
        return None

    q1 = float(s.quantile(0.25))
    q3 = float(s.quantile(0.75))
    iqr = q3 - q1

    if iqr <= 0:
        return None

    far = s[(s > q3 + 3 * iqr) | (s < q1 - 3 * iqr)]

    if far.empty or (float(s.max()) - float(s.min())) / iqr < 20:
        return None

    far_value = float(far.loc[(far - s.median()).abs().idxmax()])

    return {
        'count': int(len(far)),
        'extreme_value': clean_scalar(far_value),
        'typical_low': clean_scalar(q1),
        'typical_high': clean_scalar(q3),
        'note': (
            f'Extreme value: {len(far)} value(s) lie far outside the typical '
            f'range ({_number_text(q1)} to {_number_text(q3)}), the most '
            f'extreme being {_number_text(far_value)}. They stretch this '
            f'histogram so the bulk of the data looks squeezed. Original '
            f'values are unchanged; see the box plot.'
        )
    }


# =========================================================
# DUPLICATE GROUPS
# =========================================================

# =========================================================
# BASIC DATA TYPE
# =========================================================

def column_kind(dtype):
    if pd.api.types.is_bool_dtype(dtype):
        return 'bool'

    if pd.api.types.is_integer_dtype(dtype):
        return 'int'

    if pd.api.types.is_float_dtype(dtype):
        return 'float'

    if pd.api.types.is_datetime64_any_dtype(dtype):
        return 'date'

    return 'object'


# =========================================================
# COLUMN PROFILING HELPERS
# =========================================================

STRONG_ID_NAME_PATTERNS = [
    r'(^|_)id(_|$)',
    r'identifier',
    r'(^|_)(uuid|guid)(_|$)',
    (
        r'(student|employee|customer|user|account|order|transaction|'
        r'product|invoice|ticket|review|patient|member|booking|item|'
        r'sku|client|vendor|supplier)_?(id|no|num|number)$'
    ),
    r'roll_?(no|num|number)',
    r'registration_?(no|num|number)',
    r'(invoice|receipt|reference|ref|serial)_?(no|num|number)$',
]

WEAK_ID_NAME_PATTERNS = [
    r'code$',
    r'^code',
]

ID_NAME_PATTERNS = STRONG_ID_NAME_PATTERNS + WEAK_ID_NAME_PATTERNS


DATE_NAME_PATTERNS = [
    'date',
    'time',
    'timestamp',
    'dob',
    'birth',
    'joining',
    'joined',
    'created',
    'updated',
    'modified',
    'deadline',
]


def normalized_column_name(name):
    return re.sub(
        r'[^a-z0-9]+',
        '_',
        str(name).strip().lower()
    ).strip('_')


def has_strong_id_name(name):
    normalized = normalized_column_name(name)

    return any(
        re.search(pattern, normalized)
        for pattern in STRONG_ID_NAME_PATTERNS
    )


def has_id_like_name(name):
    normalized = normalized_column_name(name)

    for pattern in ID_NAME_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


def has_date_like_name(name):
    normalized = normalized_column_name(name)

    return any(
        token in normalized
        for token in DATE_NAME_PATTERNS
    )


def safe_unique_ratio(series):
    non_null = series.dropna()

    if len(non_null) == 0:
        return 0.0

    return float(
        non_null.nunique(dropna=True)
        / len(non_null)
    )


def numeric_conversion_ratio(series):
    """Share of non-missing cells that can be read as numbers."""
    return float(
        numeric_profile(series)['ratio']
    )


def date_conversion_ratio(series):
    """Share of non-missing cells that are valid dates."""
    present = int(series.notna().sum())

    if present == 0:
        return 0.0

    try:
        parsed, _ = parse_date_series(series)
    except Exception:
        return 0.0

    return float(parsed.notna().sum() / present)


def looks_like_date_series(series, column_name):
    """
    Detect date-like columns (real datetimes or text such as
    '2024-01-01', '01/15/2024', 'March 5 2024', 'August 1, 2024')
    without turning ordinary numbers into dates.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    if not is_text_dtype(series):
        return False

    if series.notna().sum() == 0:
        return False

    ratio = date_conversion_ratio(series)

    # A date-like column name is a supporting signal, not the proof:
    # the values themselves still have to parse as dates.
    if has_date_like_name(column_name):
        return ratio >= 0.60

    return ratio >= 0.80


def _integer_valued(values):
    return bool(
        len(values)
        and np.allclose(values, np.round(values))
    )


def is_sequential_numeric(series):
    """
    Detect a simple sequential pattern such as
    1, 2, 3, 4, 5 or 1001, 1002, 1003...
    """
    numeric = numeric_values(series)

    if len(numeric) < 5:
        return False

    values = numeric.to_numpy()

    if not _integer_valued(values):
        return False

    differences = np.diff(values)

    if len(differences) == 0:
        return False

    return bool(
        np.allclose(
            differences,
            differences[0]
        )
        and differences[0] != 0
    )


def is_counter_like(series):
    """
    A bare counter: consecutive integers (step 1) that start at 0/1 or at
    a large number (1001, 100000...), with no year-like range.

    Consecutive integers such as ages 20..49 are NOT treated as a counter:
    without an identifier-like name that would label real measurements
    as IDs.
    """
    numeric = numeric_values(series)

    if len(numeric) < 10:
        return False

    values = numeric.to_numpy()

    if not _integer_valued(values):
        return False

    differences = np.diff(values)

    if not np.allclose(np.abs(differences), 1):
        return False

    if not (
        np.all(differences == differences[0])
    ):
        return False

    lowest = values.min()
    highest = values.max()

    if 1900 <= lowest and highest <= 2100:
        return False

    return bool(lowest <= 1 or lowest >= 1000)


def has_fixed_width_long_digits(series):
    """
    Phone-number-like columns: integers that all have the same long
    digit count (>= 9 digits) and are almost all unique.
    """
    numeric = numeric_values(series)

    if len(numeric) < 10:
        return False

    values = numeric.to_numpy()

    if not _integer_valued(values):
        return False

    digits = {
        len(str(int(abs(v))))
        for v in values
    }

    return (
        len(digits) == 1
        and next(iter(digits)) >= 9
        and safe_unique_ratio(series) >= 0.90
    )


_UUID_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

_PHONE_RE = re.compile(r'^\+?[\d\s\-().]{7,20}$')

# ORD-1000, R0001, INV2024-005, EMP001, TXN_889123
_CODE_RE = re.compile(r'^[A-Za-z]{0,6}[-_#]?\d{2,}[A-Za-z0-9\-_]*$')


def id_like_value_ratio(values):
    """
    Share of text values whose STRUCTURE looks like an identifier
    (UUID, e-mail, phone number, or a prefixed code such as ORD-1001).
    """
    text = pd.Series(values).dropna().astype(str).str.strip()

    if len(text) == 0:
        return 0.0

    matches = (
        text.str.match(_UUID_RE)
        | text.str.match(_EMAIL_RE)
        | text.str.match(_CODE_RE)
        | (
            text.str.match(_PHONE_RE)
            & (text.str.count(r'\d') >= 7)
        )
    )

    return float(matches.mean())


def is_identifier_column(series, column_name):
    """
    Determine whether a column is probably an identifier.

    Several independent signals are combined; uniqueness or being
    numeric is never enough on its own.
    """
    non_null = series.dropna()

    if len(non_null) == 0:
        return False, 0.0

    unique_ratio = safe_unique_ratio(series)

    strong_name = has_strong_id_name(column_name)
    weak_name = has_id_like_name(column_name) and not strong_name

    numeric = numeric_values(series)
    numeric_share = len(numeric) / len(non_null)
    integer_like = (
        numeric_share >= 0.95
        and _integer_valued(numeric.to_numpy())
    )

    sequential_signal = is_sequential_numeric(series)

    structure_signal = (
        is_text_dtype(series)
        and numeric_share < 0.95
        and len(non_null) >= 10
        and id_like_value_ratio(non_null) >= 0.90
    )

    score = 0.0

    if strong_name:
        score += 0.45
    elif weak_name:
        score += 0.20

    if unique_ratio >= 0.995:
        score += 0.25
    elif unique_ratio >= 0.98:
        score += 0.18

    if sequential_signal:
        score += 0.30

    if structure_signal and unique_ratio >= 0.90:
        score += 0.35

    # Strongest practical cases.
    if strong_name and unique_ratio >= 0.90:
        return True, min(score + 0.20, 1.0)

    if strong_name and sequential_signal:
        return True, min(score + 0.20, 1.0)

    # Repeated foreign-key style IDs (Customer_ID in an orders table).
    if strong_name and integer_like:
        return True, min(max(score, 0.80), 1.0)

    if strong_name and structure_signal:
        return True, min(max(score, 0.80), 1.0)

    if weak_name and integer_like and unique_ratio >= 0.90:
        return True, min(max(score, 0.80), 1.0)

    if is_counter_like(series) and unique_ratio >= 0.98:
        return True, min(score + 0.10, 1.0)

    if has_fixed_width_long_digits(series):
        return True, min(max(score, 0.80), 1.0)

    if structure_signal and unique_ratio >= 0.90:
        return True, min(max(score, 0.80), 1.0)

    return score >= 0.75, min(score, 1.0)


TEXT_NAME_HINTS = {
    'review', 'comment', 'comments', 'description', 'details', 'feedback',
    'notes', 'note', 'remarks', 'message', 'summary', 'explanation',
    'bio', 'biography', 'address', 'reason', 'response', 'observation'
}

def classify_text_column(series, column_name=None):
    """Classify non-numeric/non-date strings as text, identifier, or category."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return 'categorical'
    values = non_null.astype(str).str.strip()
    count = len(values)
    unique_count = int(values.nunique(dropna=True))
    unique_ratio = unique_count / count
    lengths = values.str.len()
    average_length = float(lengths.mean())
    max_length = int(lengths.max())
    average_words = float(values.str.split().str.len().mean())
    punctuation_ratio = float(values.str.contains(r'[,.!?;:]', regex=True).mean())
    normalized_name = normalized_column_name(column_name) if column_name is not None else ''
    name_hint = bool(set(normalized_name.split('_')) & TEXT_NAME_HINTS)
    multi_word_share = float((values.str.split().str.len() >= 2).mean())

    # A text-like name is only a supporting signal: the values must also
    # be sentence-like (mostly several words) and not a tiny label set.
    if name_hint and multi_word_share >= 0.80 and unique_count >= 3:
        return 'text'
    if name_hint and (average_words >= 2 or average_length >= 12) and unique_ratio >= 0.20:
        return 'text'
    if average_length >= 35:
        return 'text'
    if max_length >= 100 and unique_ratio >= 0.30:
        return 'text'
    if average_words >= 6 and unique_ratio >= 0.35:
        return 'text'
    if average_words >= 4 and punctuation_ratio >= 0.25 and unique_ratio >= 0.40:
        return 'text'

    if count >= 10 and unique_ratio >= 0.85:
        if id_like_value_ratio(values) >= 0.80:
            return 'identifier'
        return 'text'

    if unique_count > 50 and unique_ratio >= 0.50:
        return 'text'
    return 'categorical'


def is_text_like(series):
    """Kept for compatibility: True when the column is free/high-cardinality text."""
    return classify_text_column(series) == 'text'


def detect_semantic_type(series, column_name):
    """
    Detect the most useful semantic type for a column.

    Returns:
        semantic_type
        role
        details
    """
    dtype = series.dtype

    if pd.api.types.is_bool_dtype(dtype):
        return 'boolean', 'categorical', {
            'numeric_ratio': 0.0,
            'date_ratio': 0.0
        }

    if pd.api.types.is_datetime64_any_dtype(dtype):
        return 'datetime', 'temporal', {
            'numeric_ratio': 0.0,
            'date_ratio': 1.0
        }

    # Native numeric columns.
    if (
        pd.api.types.is_integer_dtype(dtype)
        or pd.api.types.is_float_dtype(dtype)
    ):
        is_id, id_score = is_identifier_column(
            series,
            column_name
        )

        if is_id:
            return 'identifier', 'identifier', {
                'numeric_ratio': 1.0,
                'date_ratio': 0.0,
                'identifier_score': round(id_score, 4)
            }

        return 'numeric', 'measure', {
            'numeric_ratio': 1.0,
            'date_ratio': 0.0,
            'identifier_score': round(id_score, 4)
        }

    # Object/string columns (this includes columns pandas could not
    # type because of a few dirty cells).
    if is_text_dtype(series):

        if looks_like_date_series(series, column_name):
            return 'datetime', 'temporal', {
                'numeric_ratio': numeric_conversion_ratio(series),
                'date_ratio': round(
                    date_conversion_ratio(series),
                    4
                )
            }

        profile = numeric_profile(series)

        numeric_ratio = profile['ratio']

        is_id, id_score = is_identifier_column(
            series,
            column_name
        )

        # Mostly-numeric columns are numerical measures even when a few
        # cells are dirty; the dirty cells are reported separately as
        # type inconsistencies.
        if is_numeric_measure_profile(profile) and not is_id:
            return 'numeric', 'measure', {
                'numeric_ratio': round(numeric_ratio, 4),
                'date_ratio': 0.0,
                'identifier_score': round(id_score, 4)
            }

        if is_id:
            return 'identifier', 'identifier', {
                'numeric_ratio': round(numeric_ratio, 4),
                'date_ratio': 0.0,
                'identifier_score': round(id_score, 4)
            }

        kind = classify_text_column(series, column_name)

        if kind == 'identifier':
            return 'identifier', 'identifier', {
                'numeric_ratio': round(numeric_ratio, 4),
                'date_ratio': 0.0,
                'identifier_score': round(max(id_score, 0.8), 4)
            }

        if kind == 'text':
            return 'text', 'text', {
                'numeric_ratio': round(numeric_ratio, 4),
                'date_ratio': 0.0
            }

        return 'categorical', 'category', {
            'numeric_ratio': round(numeric_ratio, 4),
            'date_ratio': 0.0
        }

    # Pandas categorical dtype.
    if isinstance(dtype, pd.CategoricalDtype):
        return 'categorical', 'category', {
            'numeric_ratio': numeric_conversion_ratio(series),
            'date_ratio': 0.0
        }

    return 'unknown', 'other', {
        'numeric_ratio': numeric_conversion_ratio(series),
        'date_ratio': 0.0
    }


def build_column_profiles(df):
    """
    Build a universal semantic profile for every uploaded column.
    """
    profiles = []

    for name in df.columns:
        series = df[name]

        missing = int(
            series.isna().sum()
        )

        non_null_count = int(
            series.notna().sum()
        )

        missing_percent = (
            missing / len(df) * 100
            if len(df)
            else 0
        )

        unique_count = int(
            series.nunique(
                dropna=True
            )
        )

        unique_ratio = (
            unique_count / non_null_count
            if non_null_count
            else 0
        )

        semantic_type, role, details = detect_semantic_type(
            series,
            name
        )

        profiles.append({
            'name': str(name),
            'dtype': str(series.dtype),
            'kind': column_kind(series.dtype),

            # New semantic information.
            'semantic_type': semantic_type,
            'role': role,

            'missing': missing,
            'missing_percent': missing_percent,
            'unique': unique_count,

            # Useful for frontend/report logic.
            'unique_ratio': round(
                float(unique_ratio),
                4
            ),
            'non_null': non_null_count,
            'identifier_score': details.get(
                'identifier_score',
                0.0
            ),
            'numeric_ratio': details.get(
                'numeric_ratio',
                0.0
            ),
            'date_ratio': details.get(
                'date_ratio',
                0.0
            )
        })

    return profiles


# =========================================================
# COLUMN LIST HELPERS
# =========================================================

def get_columns_by_role(profiles, role):
    return [
        profile['name']
        for profile in profiles
        if profile['role'] == role
    ]


def get_columns_by_semantic_type(
    profiles,
    semantic_type
):
    return [
        profile['name']
        for profile in profiles
        if profile['semantic_type'] == semantic_type
    ]


# =========================================================
# OUTLIER DETECTION
# =========================================================

# =========================================================
# STATISTICAL OUTLIERS (IQR) - single source of truth
# =========================================================
#
# Used for the outlier counts, the outlier rows, the box-plot data and the
# zoomed charts, so the numbers can never disagree with each other.
#
#   IQR         = Q3 - Q1
#   lower bound = Q1 - 1.5 * IQR
#   upper bound = Q3 + 1.5 * IQR
#
# Quartiles use position (n * p - 0.5) with linear interpolation, which is
# exactly how Plotly (the dashboard box plot) computes them. pandas'
# default quantile uses (n - 1) * p and gives different quartiles for small
# samples, which is why counts and box plots used to disagree.
#
# IQR = 0 (most values identical): the bounds collapse to Q1 = Q3, so every
# value different from them IS outside the bounds, exactly as the box plot
# draws it. (The old code returned 0 here, but the box plot still drew the
# points.)

IQR_MIN_VALUES = 4

IQR_METHOD = (
    'IQR rule (Q1 - 1.5*IQR, Q3 + 1.5*IQR); quartiles by linear '
    'interpolation at position n*p - 0.5 (same as the box plot)'
)


def _box_find_bin(value, bins, line_low):
    """Binary search used by Plotly to place the whisker fences (ported
    from plotly.js `Lib.findBin`, including its 1e-9 rounding tolerance)."""
    n1 = 0
    n2 = len(bins)

    bin_size = (bins[-1] - bins[0]) / (n2 - 1) if n2 > 1 else 1.0

    value += bin_size * 1e-9 * (-1 if line_low else 1)

    while n1 < n2:
        n = (n1 + n2) // 2

        below = bins[n] < value if line_low else bins[n] <= value

        if below:
            n1 = n + 1
        else:
            n2 = n

    return n1 - 1


def iqr_outlier_analysis(values):
    """
    Statistical outliers of the VALID numeric values only: missing and
    non-numeric cells must already be excluded (or are dropped here).
    """
    numeric = pd.to_numeric(
        pd.Series(values),
        errors='coerce'
    ).astype('float64')

    array = np.sort(
        numeric[np.isfinite(numeric)].to_numpy()
    )

    result = {
        'n': int(len(array)),
        'evaluated': bool(len(array) >= IQR_MIN_VALUES),
        'method': IQR_METHOD,
        'q1': None,
        'median': None,
        'q3': None,
        'iqr': None,
        'iqr_zero': False,
        'lower_bound': None,
        'upper_bound': None,
        'lower_whisker': None,
        'upper_whisker': None,
        'low_count': 0,
        'high_count': 0,
        'count': 0,
        'outlier_values': []
    }

    if not result['evaluated']:
        return result

    q1 = float(np.quantile(array, 0.25, method='hazen'))
    median = float(np.quantile(array, 0.50, method='hazen'))
    q3 = float(np.quantile(array, 0.75, method='hazen'))

    iqr = q3 - q1

    # Bounds: Q1 - 1.5*IQR and Q3 + 1.5*IQR, written the way the box plot
    # writes them (2.5*Q1 - 1.5*Q3 ...) so floating-point rounding matches.
    lower = 2.5 * q1 - 1.5 * q3
    upper = 2.5 * q3 - 1.5 * q1

    last = len(array) - 1

    # Whisker ends = the most extreme values still inside the bounds; the
    # box plot draws exactly the values beyond them as outlier points.
    lower_fence = min(
        q1,
        float(array[min(_box_find_bin(lower, array, True) + 1, last)])
    )
    upper_fence = max(
        q3,
        float(array[max(_box_find_bin(upper, array, False), 0)])
    )

    low = array[array < lower_fence]
    high = array[array > upper_fence]

    result.update({
        'q1': q1,
        'median': median,
        'q3': q3,
        'iqr': iqr,
        'iqr_zero': bool(iqr == 0),
        'lower_bound': lower,
        'upper_bound': upper,
        'lower_whisker': lower_fence,
        'upper_whisker': upper_fence,
        'low_count': int(len(low)),
        'high_count': int(len(high)),
        'count': int(len(low) + len(high)),
        'outlier_values': [
            clean_scalar(v)
            for v in np.unique(np.concatenate([low, high]))[:20]
        ]
    })

    return result


def outlier_count(s):
    # Only the valid numeric values take part; dirty cells are ignored.
    return iqr_outlier_analysis(
        numeric_values(s)
    )['count']


def box_plot_stats(analysis):
    """Box-plot numbers taken from the same analysis as the outlier count."""
    keys = (
        'n', 'evaluated', 'q1', 'median', 'q3', 'iqr', 'iqr_zero',
        'lower_bound', 'upper_bound', 'lower_whisker', 'upper_whisker',
        'low_count', 'high_count', 'count', 'method'
    )

    return {k: analysis[k] for k in keys}


def outlier_note(analysis):
    """Short explanation shown with the box plot."""
    if not analysis['evaluated']:
        return (
            f"Outliers not evaluated: fewer than {IQR_MIN_VALUES} numeric values."
        )

    text = (
        f"Statistical outliers (IQR rule): {analysis['count']} "
        f"({analysis['low_count']} below, {analysis['high_count']} above); "
        f"bounds {_number_text(analysis['lower_bound'])} to "
        f"{_number_text(analysis['upper_bound'])}."
    )

    if analysis['iqr_zero']:
        text += (
            ' IQR is 0 (most values are identical), so every value different '
            'from Q1/Q3 lies outside the bounds.'
        )

    return text


# =========================================================
# BUSINESS-RULE VALIDATION
# =========================================================
#
# Business rules are DATA-QUALITY rules ("a quantity must be 1-5"), not
# statistical ones. They are reported separately from IQR outliers; a value
# can be both. Rules are matched by normalized column name (case and
# separators ignored). To validate another column, add an entry here;
# no other code changes.
#
# Nothing is deleted or modified: invalid values stay in the dataset and in
# every chart. They are only reported, and a separate "valid values only"
# statistics row is produced for rule columns.

BUSINESS_RULES = {
    'quantity': {'min': 1, 'max': 5},
    'customer_rating': {'min': 1, 'max': 5},
}


def business_rule_text(rule):
    return f"{_number_text(rule['min'])}-{_number_text(rule['max'])}"


def detect_business_rule_violations(df):
    source_rows = source_row_numbers(df)

    result = []

    for name in df.columns:

        rule = BUSINESS_RULES.get(normalized_column_name(name))

        if rule is None:
            continue

        values, _, non_numeric_mask = parse_numeric_series(df[name])

        if not values.notna().any():
            continue

        below = (values < rule['min']).to_numpy()
        above = (values > rule['max']).to_numpy()
        violation = below | above
        in_range = (values >= rule['min']) & (values <= rule['max'])

        analysis = iqr_outlier_analysis(values.dropna())

        if analysis['evaluated']:
            statistical = (
                (values < analysis['lower_whisker'])
                | (values > analysis['upper_whisker'])
            ).to_numpy()
        else:
            statistical = np.zeros(len(values), dtype=bool)

        positions = np.flatnonzero(violation)

        grouped = {}

        for position in positions:
            raw = clean_scalar(df[name].iloc[position])

            key = _stable_key_value(raw)

            grouped.setdefault(key, {'value': raw, 'rows': []})

            grouped[key]['rows'].append(int(source_rows[position]))

        invalid_values = sorted(
            (
                {
                    'value': item['value'],
                    'count': len(item['rows']),
                    'row_numbers': item['rows']
                }
                for item in grouped.values()
            ),
            key=lambda v: (-v['count'], v['row_numbers'][0])
        )

        valid_series = values[in_range]

        item = {
            'column': str(name),
            'rule': {
                'min': rule['min'],
                'max': rule['max']
            },
            'rule_text': business_rule_text(rule),
            'total_rows': int(len(df)),
            'valid_count': int(in_range.sum()),
            'invalid_count': int(violation.sum()),
            'below_range_count': int(below.sum()),
            'above_range_count': int(above.sum()),
            'missing_count': int(df[name].isna().sum()),
            'non_numeric_count': int(non_numeric_mask.sum()),
            'invalid_values': invalid_values,
            'row_numbers': [int(source_rows[p]) for p in positions],
            # Classification: a violation may ALSO be a statistical outlier.
            'also_statistical_outliers': int((violation & statistical).sum()),
            'violations_not_statistical_outliers': int((violation & ~statistical).sum()),
            'statistical_outliers_not_violations': int((~violation & statistical).sum()),
            'valid_statistics': (
                {
                    'min': pretty(valid_series.min()),
                    'max': pretty(valid_series.max()),
                    'mean': pretty(valid_series.mean()),
                    'median': pretty(valid_series.median()),
                    'std': (
                        pretty(valid_series.std(ddof=1))
                        if len(valid_series) > 1
                        else 0
                    ),
                    'count': int(len(valid_series))
                }
                if len(valid_series)
                else None
            )
        }

        shown = ', '.join(
            f"{v['value']} x{v['count']} ({_rows_text(v['row_numbers'], 4)})"
            for v in invalid_values[:6]
        )

        item['message'] = (
            f"{name}: {item['invalid_count']} value(s) violate the business "
            f"rule {item['rule_text']}"
            + (f" ({shown})" if shown else '')
            + '.'
        )

        result.append(item)

    return result


# =========================================================
# TYPE INCONSISTENCY DETECTION
# =========================================================

def _examples(values, limit=5):
    seen = []

    for value in values:
        text = str(value).strip()

        if text not in seen:
            seen.append(text)

        if len(seen) >= limit:
            break

    return seen


def detect_type_inconsistencies(
    df,
    profiles
):
    """
    Report cells that do not fit the inferred meaning of a column,
    while the valid cells keep being used for the analysis.

        numeric measure   -> non-numeric cells ("Twenty Seven", "unknown")
                             and numbers needing cleanup ("60,000", "$5")
        date column       -> invalid dates ("not-a-date") and mixed formats
    """
    inconsistent = []

    for profile in profiles:
        name = profile['name']
        role = profile['role']
        series = df[name]

        non_null = series.dropna()

        if len(non_null) == 0 or not is_text_dtype(series):
            continue

        # ---------------------------------------------------------
        # NUMERIC MEASURE WITH DIRTY CELLS
        # ---------------------------------------------------------
        if role == 'measure':
            values, formatted_mask, invalid_mask = parse_numeric_series(
                series
            )

            invalid_count = int(invalid_mask.sum())
            formatted_count = int(formatted_mask.sum())

            if not invalid_count and not formatted_count:
                continue

            invalid_examples = _examples(series[invalid_mask])
            formatted_examples = _examples(series[formatted_mask])

            parts = []

            if invalid_count:
                parts.append(
                    f'{invalid_count} non-numeric value(s): '
                    + ', '.join(invalid_examples[:3])
                )

            if formatted_count:
                parts.append(
                    f'{formatted_count} number(s) needing cleanup: '
                    + ', '.join(formatted_examples[:3])
                )

            inconsistent.append({
                'name': name,
                'type': (
                    'numeric_with_invalid_values'
                    if invalid_count
                    else 'numeric_with_formatting'
                ),
                'numeric_ratio': round(
                    float(values.notna().sum() / len(non_null)),
                    4
                ),
                'invalid_count': invalid_count,
                'formatted_count': formatted_count,
                'invalid_examples': invalid_examples,
                'formatted_examples': formatted_examples,
                'summary': '; '.join(parts),
                'message': (
                    'Column is numeric but contains values that are '
                    'not clean numbers: ' + '; '.join(parts) + '.'
                )
            })

            continue

        # ---------------------------------------------------------
        # DATE COLUMN WITH INVALID / MIXED-FORMAT CELLS
        # ---------------------------------------------------------
        if role == 'temporal':
            parsed, _ = parse_date_series(series)

            present = series.notna()

            invalid_mask = present & parsed.isna()

            invalid_count = int(invalid_mask.sum())

            valid_text = series[present & parsed.notna()]

            valid_text = valid_text[
                valid_text.map(lambda v: isinstance(v, str))
            ]

            format_count = len({
                date_format_signature(v)
                for v in valid_text
            })

            if not invalid_count and format_count < 2:
                continue

            invalid_examples = _examples(series[invalid_mask])

            parts = []

            if invalid_count:
                parts.append(
                    f'{invalid_count} invalid date(s): '
                    + ', '.join(invalid_examples[:3])
                )

            if format_count >= 2:
                parts.append(
                    f'dates written in {format_count} different formats'
                )

            inconsistent.append({
                'name': name,
                'type': (
                    'mixed_date'
                    if invalid_count
                    else 'mixed_date_format'
                ),
                'date_ratio': round(
                    float(parsed.notna().sum() / len(non_null)),
                    4
                ),
                'invalid_count': invalid_count,
                'format_count': int(format_count),
                'invalid_examples': invalid_examples,
                'summary': '; '.join(parts),
                'message': (
                    'Column contains date values with problems: '
                    + '; '.join(parts) + '.'
                )
            })

    return inconsistent


# =========================================================
# CATEGORICAL CHART SELECTION
# =========================================================

TOP_CATEGORIES = 10


def should_visualize_categorical(df, column_name):
    series = df[column_name].dropna()
    if len(series) == 0:
        return False
    if is_text_dtype(series):
        counts = series.map(normalized_text_value).value_counts()
    else:
        counts = series.astype(str).value_counts()
    unique_count = int(len(counts))
    unique_ratio = unique_count / len(series)
    if unique_count <= 1:
        return False
    if len(series) >= 10 and unique_ratio >= 0.90:
        return False
    if unique_count > 50 and unique_ratio > 0.50:
        return False
    if unique_count > 30 and counts.head(TOP_CATEGORIES).sum() / len(series) < 0.25:
        return False
    return True


def build_categorical_chart(name, series):
    """Frequency chart with case/whitespace-normalized text categories."""
    non_null = series.dropna()
    if non_null.empty:
        return None

    if is_text_dtype(series):
        normalized = non_null.map(normalized_text_value)
        counts = normalized.value_counts()
        label_map = {}
        for norm in counts.index:
            originals = non_null[normalized == norm].astype(str).str.strip()
            label_map[norm] = originals.value_counts().index[0]
        labels = [label_map[v] for v in counts.index]
    else:
        counts = non_null.astype(str).value_counts()
        labels = counts.index.tolist()

    total_categories = int(len(counts))
    top_counts = counts.head(TOP_CATEGORIES)
    top_labels = [
        label_map[v] if is_text_dtype(series) else str(v)
        for v in top_counts.index
    ]
    top_labels = [
        label if len(label) <= 28 else label[:27] + '…'
        for label in top_labels
    ]
    longest = max((len(label) for label in top_labels), default=0)

    hover = None
    if is_text_dtype(series):
        hover = []
        for norm in top_counts.index:
            originals = non_null[normalized == norm].astype(str).value_counts()
            hover.append(
                ', '.join(f"'{v}' x{int(c)}" for v, c in originals.items())
                if len(originals) > 1 else ''
            )
        if not any(hover):
            hover = None

    if total_categories <= 6 and longest <= 16:
        return {
            'title': f'{name} Frequency',
            'data': [{
                'type': 'bar',
                'x': top_labels,
                'y': top_counts.values.tolist(),
                'marker': {'color': '#b54cff'},
                **({'hovertext': hover} if hover else {})
            }],
            'layout': {
                'xaxis': {'title': str(name)},
                'yaxis': {'title': 'Count'}
            }
        }

    title = (
        f'{name} Frequency'
        if total_categories <= TOP_CATEGORIES
        else f'{name} Frequency (Top {len(top_counts)} of {total_categories})'
    )
    return {
        'title': title,
        'data': [{
            'type': 'bar',
            'orientation': 'h',
            'x': top_counts.values.tolist(),
            'y': top_labels,
            'marker': {'color': '#b54cff'},
            **({'hovertext': hover} if hover else {})
        }],
        'layout': {
            'xaxis': {'title': 'Count'},
            'yaxis': {'title': '', 'autorange': 'reversed', 'automargin': True}
        }
    }


# =========================================================
# ADAPTIVE DATE AGGREGATION
# =========================================================

MAX_DATE_BARS = 30

_DATE_GRANULARITIES = [
    ('D', 'Daily'),
    ('W', 'Weekly'),
    ('M', 'Monthly'),
    ('Q', 'Quarterly'),
    ('Y', 'Yearly'),
]


def build_date_counts(dates):
    """
    Choose the finest time granularity that still gives a readable
    number of bars (<= MAX_DATE_BARS) for the actual date range, then
    count records per period (empty periods show as 0).

    Returns (labels, counts, granularity_name).
    """
    low = dates.min()
    high = dates.max()

    chosen = _DATE_GRANULARITIES[-1]

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')

        for freq, label in _DATE_GRANULARITIES:
            bars = (
                high.to_period(freq) - low.to_period(freq)
            ).n + 1

            if bars <= MAX_DATE_BARS:
                chosen = (freq, label)
                break

        freq, granularity = chosen

        periods = dates.dt.to_period(freq)

        full_range = pd.period_range(
            low.to_period(freq),
            high.to_period(freq),
            freq=freq
        )

        counts = (
            periods
            .value_counts()
            .reindex(full_range, fill_value=0)
            .sort_index()
        )

    def label_for(period):
        if freq == 'D':
            return period.start_time.strftime('%Y-%m-%d')

        if freq == 'W':
            return period.start_time.strftime('%Y-%m-%d')

        if freq == 'M':
            return period.start_time.strftime('%b %Y')

        if freq == 'Q':
            return f'{period.year} Q{period.quarter}'

        return str(period.year)

    return (
        [label_for(p) for p in counts.index],
        [int(v) for v in counts.values],
        granularity
    )


# =========================================================
# MAIN ANALYSIS
# =========================================================

def analyze_dataframe(df: pd.DataFrame):
    source_rows = df.attrs.get('source_rows')

    df = df.copy()

    # ---------------------------------------------------------
    # BASIC DATASET INFORMATION
    # ---------------------------------------------------------

    # Normalize common textual missing values before analysis.
    df = normalize_missing_values(df)

    if source_rows is not None:
        df.attrs['source_rows'] = source_rows

    rows, cols = df.shape

    # Empty datasets are still valid analysis inputs. Keep the response
    # contract intact while allowing every downstream section to render
    # an appropriate empty state.
    missing_series = df.isna().sum()

    # ---------------------------------------------------------
    # UNIVERSAL COLUMN PROFILING
    # ---------------------------------------------------------

    column_profiles = build_column_profiles(
        df
    )

    # Semantic analysis results.
    numeric_cols = get_columns_by_role(
        column_profiles,
        'measure'
    )

    categorical_cols = get_columns_by_role(
        column_profiles,
        'category'
    )

    text_cols = get_columns_by_role(
        column_profiles,
        'text'
    )

    date_cols = get_columns_by_role(
        column_profiles,
        'temporal'
    )

    identifier_cols = get_columns_by_role(
        column_profiles,
        'identifier'
    )

    # Duplicate records are compared using non-identifier columns.
    # An identifier changing does not make an otherwise identical record new.
    duplicate_analysis = build_duplicate_analysis(
        df,
        identifier_cols
    )
    duplicate_groups = duplicate_analysis['groups']

    duplicate_row_mask = pd.Series(False, index=df.index)
    if duplicate_analysis['repeat_positions']:
        duplicate_row_mask.iloc[
            duplicate_analysis['repeat_positions']
        ] = True

    # `duplicate_rows` keeps its original meaning: exact duplicates.
    duplicate_count = duplicate_analysis['exact_duplicate_rows']
    duplicates_ignoring_identifiers = (
        duplicate_analysis['duplicate_rows_ignoring_identifiers']
    )

    identifier_duplicates = detect_identifier_duplicates(
        df,
        identifier_cols
    )
    identifier_anomalies = detect_identifier_anomalies(
        df,
        identifier_cols
    )
    text_inconsistencies = detect_text_inconsistencies(
        df,
        column_profiles
    )
    placeholder_values = detect_placeholder_values(
        df,
        column_profiles
    )

    # ---------------------------------------------------------
    # COLUMN PROFILE
    # ---------------------------------------------------------

    columns = []

    for profile in column_profiles:

        name = profile['name']

        # Preserve the original column profile fields.
        # Add semantic information for the improved engine.
        columns.append({
            'name': name,
            'dtype': profile['dtype'],
            'kind': profile['kind'],

            'semantic_type': profile[
                'semantic_type'
            ],

            'role': profile['role'],

            'missing': profile['missing'],
            'missing_percent': profile[
                'missing_percent'
            ],

            'unique': profile['unique'],

            'unique_ratio': profile[
                'unique_ratio'
            ],

            'non_null': profile[
                'non_null'
            ],

            'identifier_score': profile[
                'identifier_score'
            ],

            'numeric_ratio': profile[
                'numeric_ratio'
            ],

            'date_ratio': profile[
                'date_ratio'
            ]
        })

    # ---------------------------------------------------------
    # NUMERICAL STATISTICS
    # ---------------------------------------------------------

    # Business rules are evaluated once and reused by the statistics, the
    # charts, the outlier classification and the quality findings.
    business_rules = detect_business_rule_violations(df)

    rule_by_column = {
        item['column']: item
        for item in business_rules
    }

    stats = []

    for name in numeric_cols:

        numeric_all, _, non_numeric_mask = parse_numeric_series(
            df[name]
        )

        s = numeric_all.dropna()

        if len(s):

            # Statistics of the RAW numeric values (nothing excluded
            # except missing / non-numeric cells).
            stats.append({
                'name': str(name),
                'min': pretty(s.min()),
                'max': pretty(s.max()),
                'mean': pretty(s.mean()),
                'median': pretty(s.median()),
                'std': (
                    pretty(
                        s.std(
                            ddof=1
                        )
                    )
                    if len(s) > 1
                    else 0
                ),
                'basis': 'raw numeric values',
                'count': int(len(s)),
                'non_numeric_count': int(non_numeric_mask.sum()),
                'missing_count': int(df[name].isna().sum())
            })

            rule = rule_by_column.get(str(name))

            # Statistics of the VALID business values only: values that
            # break the business rule are excluded here (and only here).
            if rule and rule['valid_statistics']:

                valid_stats = rule['valid_statistics']

                stats.append({
                    'name': (
                        f"{name} (valid values only, "
                        f"rule {rule['rule_text']})"
                    ),
                    'column': str(name),
                    'min': valid_stats['min'],
                    'max': valid_stats['max'],
                    'mean': valid_stats['mean'],
                    'median': valid_stats['median'],
                    'std': valid_stats['std'],
                    'basis': (
                        f"valid values within business rule "
                        f"{rule['rule_text']}"
                    ),
                    'count': valid_stats['count'],
                    'excluded_invalid_count': rule['invalid_count'],
                    'non_numeric_count': int(non_numeric_mask.sum()),
                    'missing_count': int(df[name].isna().sum())
                })

    # ---------------------------------------------------------
    # MISSING VALUE ANALYSIS
    # ---------------------------------------------------------

    missing = []

    for c in df.columns:

        count = int(
            missing_series[c]
        )

        percent = (
            (count / rows * 100)
            if rows
            else 0
        )

        missing.append({
            'name': str(c),
            'count': count,
            'percent': percent
        })

    # Only columns which actually contain missing values.
    nonzero_missing = [
        x for x in missing
        if x['count'] > 0
    ]

    # ---------------------------------------------------------
    # CHART DATA
    # ---------------------------------------------------------

    charts = []

    # Missing values chart.
    if nonzero_missing:

        charts.append({
            'title': 'Missing Values by Column',

            'data': [{
                'type': 'bar',
                'x': [
                    x['name']
                    for x in nonzero_missing
                ],
                'y': [
                    x['count']
                    for x in nonzero_missing
                ],
                'marker': {
                    'color': '#ff4f70'
                }
            }],

            'layout': {
                'xaxis': {
                    'title': ''
                },
                'yaxis': {
                    'title': 'Missing cells'
                }
            }
        })

    # ---------------------------------------------------------
    # NUMERICAL DISTRIBUTIONS
    # ---------------------------------------------------------

    # Analyze all meaningful numerical columns rather than
    # arbitrarily taking the first three numeric dtypes.
    extreme_skew = []

    outlier_analysis = {}

    for name in numeric_cols:

        vals = numeric_values(df[name]).tolist()

        skew = describe_extreme_skew(vals)

        if skew:
            extreme_skew.append({'name': str(name), **skew})

        if vals:

            # The SAME analysis feeds the outlier count, the box plot and
            # the zoomed charts.
            analysis = iqr_outlier_analysis(vals)

            outlier_analysis[str(name)] = analysis

            _, _, invalid_numeric = parse_numeric_series(df[name])

            numeric_counts_note = (
                f"Numeric values: {len(vals)} \u00b7 "
                f"non-numeric: {int(invalid_numeric.sum())} \u00b7 "
                f"missing: {int(df[name].isna().sum())}."
            )

            rule = rule_by_column.get(str(name))

            if rule:
                numeric_counts_note += (
                    f" Business rule {rule['rule_text']}: "
                    f"{rule['valid_count']} valid \u00b7 "
                    f"{rule['invalid_count']} invalid "
                    f"(kept in the chart, reported separately)."
                )

            # Histogram.
            charts.append({
                'title': f'{name} Distribution',

                'data': [{
                    'type': 'histogram',
                    'x': vals,
                    'marker': {
                        'color': '#6b4cff'
                    }
                }],

                'layout': {
                    'xaxis': {
                        'title': str(name)
                    },
                    'yaxis': {
                        'title': 'Frequency'
                    }
                }
            })

            if skew:
                charts[-1]['note'] = skew['note']
            charts[-1]['note'] = (charts[-1].get('note', '') + ' ' + numeric_counts_note).strip()

            # Box plot: the points drawn beyond the whiskers are exactly the
            # outliers counted in `analysis` (same data, same rule).
            charts.append({
                'title': f'{name} Box Plot',
                'note': (outlier_note(analysis) + ' ' + numeric_counts_note).strip(),
                'box_stats': box_plot_stats(analysis),

                'data': [{
                    'type': 'box',
                    'x': vals,
                    'orientation': 'h',
                    'name': str(name),
                    'boxpoints': (
                        'outliers'
                        if analysis['evaluated']
                        else False
                    ),
                    'quartilemethod': 'linear',
                    'marker': {
                        'color': '#29b6ff'
                    },
                    'line': {
                        'color': '#29b6ff'
                    }
                }],

                'layout': {
                    'xaxis': {
                        'title': str(name)
                    },
                    'yaxis': {
                        'title': ''
                    }
                }
            })

            if skew and analysis['evaluated'] and analysis['iqr'] > 0:
                zoom_low = analysis['lower_bound']
                zoom_high = analysis['upper_bound']
                charts.append({
                    'title': f'{name} Distribution (Zoomed: Typical Range)',
                    'note': f"Zoomed to the typical range ({_number_text(zoom_low)} to {_number_text(zoom_high)}); all original values remain represented in the main histogram and box plot. {numeric_counts_note}",
                    'data': [{'type': 'histogram', 'x': vals, 'marker': {'color': '#6b4cff'}}],
                    'layout': {
                        'xaxis': {'title': str(name), 'range': [zoom_low, zoom_high]},
                        'yaxis': {'title': 'Frequency'}
                    }
                })
                charts.append({
                    'title': f'{name} Box Plot (Zoomed: Typical Range)',
                    'note': f"Zoomed to the typical range ({_number_text(zoom_low)} to {_number_text(zoom_high)}); original values are unchanged. {outlier_note(analysis)} {numeric_counts_note}",
                    'box_stats': box_plot_stats(analysis),
                    'data': [{
                        'type': 'box',
                        'x': vals,
                        'orientation': 'h',
                        'name': str(name),
                        'boxpoints': 'outliers',
                        'quartilemethod': 'linear',
                        'marker': {'color': '#29b6ff'},
                        'line': {'color': '#29b6ff'}
                    }],
                    'layout': {
                        'xaxis': {'title': str(name), 'range': [zoom_low, zoom_high]},
                        'yaxis': {'title': ''}
                    }
                })

    # ---------------------------------------------------------
    # CATEGORICAL FREQUENCY
    # ---------------------------------------------------------

    # Only meaningful categorical columns are considered.
    # High-cardinality/free-form text is skipped.
    visual_categorical_cols = [
        c
        for c in categorical_cols
        if should_visualize_categorical(
            df,
            c
        )
    ]

    for name in visual_categorical_cols:

        chart = build_categorical_chart(
            name,
            df[name]
        )

        if chart:
            charts.append(chart)

    # ---------------------------------------------------------
    # DATE/TIME INFORMATION
    # ---------------------------------------------------------

    date_analysis = []

    for name in date_cols:

        try:
            converted, _ = parse_date_series(
                df[name]
            )
        except Exception:
            converted = pd.Series(
                pd.NaT,
                index=df.index
            )

        valid_dates = converted.dropna()

        present_count = int(
            df[name].notna().sum()
        )

        invalid_date_mask = (
            df[name].notna() & converted.isna()
        ).to_numpy()

        invalid_positions = np.flatnonzero(invalid_date_mask)

        date_source_rows = source_row_numbers(df)

        item = {
            'name': str(name),
            'min': (
                valid_dates.min().isoformat()
                if pd.notna(valid_dates.min())
                else None
            ),
            'max': (
                valid_dates.max().isoformat()
                if pd.notna(valid_dates.max())
                else None
            ),
            'valid_count': int(
                len(valid_dates)
            ),
            # Cells that are present but are not valid dates.
            'invalid_count': int(
                present_count
                - len(valid_dates)
            ),
            'missing_count': int(df[name].isna().sum()),
            'total_rows': int(len(df)),
            # Invalid dates are reported, never charted or used for the range.
            'invalid_examples': _examples(
                df[name].iloc[invalid_positions]
            ),
            'invalid_row_numbers': [
                int(date_source_rows[p])
                for p in invalid_positions
            ],
            'day_first_inferred': bool(
                is_text_dtype(df[name])
                and infer_day_first(
                    df[name].dropna().astype(str).str.strip()
                )
            )
        }

        # Adaptive date visualization: the time granularity is chosen
        # from the actual date range so the chart stays readable.
        if len(valid_dates) > 1:

            try:
                labels, counts, granularity = (
                    build_date_counts(
                        valid_dates
                    )
                )

                item['granularity'] = granularity

                charts.append({
                    'title': (
                        f'{name} Over Time '
                        f'({granularity})'
                    ),

                    'note': (
                        f"{item['valid_count']} valid date(s) charted; "
                        f"{item['invalid_count']} invalid and "
                        f"{item['missing_count']} missing excluded."
                    ),

                    'data': [{
                        'type': 'bar',
                        'x': labels,
                        'y': counts,
                        'marker': {
                            'color': '#29b6ff'
                        }
                    }],

                    'layout': {
                        'xaxis': {
                            'title': str(name),
                            'type': 'category',
                            'tickangle': (
                                -45
                                if len(labels) > 8
                                else 0
                            ),
                            'nticks': 12
                        },
                        'yaxis': {
                            'title': 'Records'
                        }
                    }
                })

            except Exception:
                pass

        date_analysis.append(item)

    # ---------------------------------------------------------
    # OUTLIER DETECTION
    # ---------------------------------------------------------

    outliers = []

    outlier_source_rows = source_row_numbers(df)

    for name in numeric_cols:

        analysis = (
            outlier_analysis.get(str(name))
            or iqr_outlier_analysis(
                numeric_values(df[name])
            )
        )

        if analysis['count']:

            numeric_all, _, _ = parse_numeric_series(df[name])

            outside = (
                (numeric_all < analysis['lower_whisker'])
                | (numeric_all > analysis['upper_whisker'])
            ).to_numpy()

            rule = rule_by_column.get(str(name))

            outliers.append({
                'name': str(name),
                'count': analysis['count'],
                'low_count': analysis['low_count'],
                'high_count': analysis['high_count'],
                'q1': analysis['q1'],
                'q3': analysis['q3'],
                'iqr': analysis['iqr'],
                'iqr_zero': analysis['iqr_zero'],
                'lower_bound': analysis['lower_bound'],
                'upper_bound': analysis['upper_bound'],
                'method': analysis['method'],
                'outlier_values': analysis['outlier_values'],
                'row_numbers': [
                    int(outlier_source_rows[p])
                    for p in np.flatnonzero(outside)
                ][:100],
                # Outliers that ALSO break a business rule (counted in
                # both categories, labelled separately).
                'also_business_rule_violations': (
                    rule['also_statistical_outliers'] if rule else 0
                )
            })

    # ---------------------------------------------------------
    # TYPE INCONSISTENCY DETECTION
    # ---------------------------------------------------------

    inconsistent_details = detect_type_inconsistencies(
        df,
        column_profiles
    )

    inconsistent = [
        item['name']
        for item in inconsistent_details
    ]

    # ---------------------------------------------------------
    # CONSTANT COLUMNS
    # ---------------------------------------------------------

    constant_columns = []

    for profile in column_profiles:

        if (
            profile['non_null'] > 0
            and profile['unique'] <= 1
        ):
            constant_columns.append(
                profile['name']
            )

    # ---------------------------------------------------------
    # HIGH CARDINALITY COLUMNS
    # ---------------------------------------------------------

    high_cardinality_columns = []

    for profile in column_profiles:

        if (
            profile['non_null'] == 0
            or profile['role'] in (
                'identifier',
                'measure',
                'temporal'
            )
        ):
            continue

        near_unique = (
            profile['unique_ratio'] >= 0.90
            and profile['unique'] >= 10
        )

        very_many = (
            profile['unique'] > 50
            and profile['unique_ratio'] >= 0.50
        )

        if near_unique or very_many:
            high_cardinality_columns.append(
                profile['name']
            )

    # ---------------------------------------------------------
    # QUALITY FINDINGS
    # ---------------------------------------------------------

    findings = []

    # Missing values.
    if nonzero_missing:

        missing_column_names = ', '.join(
            x['name']
            for x in nonzero_missing
        )

        findings.append({
            'type': 'warn',
            'text': (
                f'Missing values detected in '
                f'{len(nonzero_missing)} column(s): '
                f'{missing_column_names}.'
            )
        })

    else:

        findings.append({
            'type': 'good',
            'text': 'No missing values detected.'
        })

    # Duplicates: exact duplicates and duplicates that only differ in
    # identifier columns are different things and are reported separately.
    extra_duplicates = duplicate_analysis[
        'additional_duplicate_rows_ignoring_identifiers'
    ]

    if duplicate_count:

        findings.append({
            'type': 'warn',
            'text': (
                f'{duplicate_count:,} exact duplicate record(s) in '
                f"{duplicate_analysis['exact_duplicate_groups']:,} group(s): "
                f'every column is identical.'
            )
        })

    if extra_duplicates:

        ignored_text = ', '.join(
            duplicate_analysis['ignored_identifier_columns']
        )

        findings.append({
            'type': 'warn',
            'text': (
                f'{extra_duplicates:,} additional duplicate record(s) '
                f'(not counted among the exact duplicates) detected when '
                f'identifier column(s) ({ignored_text}) are ignored: all '
                f'other fields match but the identifier values differ.'
            )
        })

    if duplicate_analysis['identifier_comparison_suppressed']:

        findings.append({
            'type': 'info',
            'text': (
                'Duplicate comparison ignoring identifier columns was not '
                'applied: the remaining columns are too generic '
                '(too many records would match).'
            )
        })

    if not duplicate_count and not extra_duplicates:

        findings.append({
            'type': 'good',
            'text': 'No duplicate records detected.'
        })

    for group in duplicate_groups[:5]:

        rows_text = _short_rows(group['row_numbers'], 8)

        kind = (
            f"{group['exact_duplicate_count']} exact duplicate(s)"
            + (
                f", {group['identifier_only_duplicate_count']} "
                f"identifier-only duplicate(s) (identifiers differ: "
                + ', '.join(group['differing_identifier_columns'])
                + ')'
                if group['identifier_only_duplicate_count']
                else ''
            )
        )

        findings.append({
            'type': 'info',
            'text': (
                f"Duplicate group {group['group_id']}: rows {rows_text} "
                f"(original: row {group['original_row']}; {kind})."
            )
        })

    # Numerical columns.
    if numeric_cols:

        findings.append({
            'type': 'good',
            'text': (
                f'{len(numeric_cols)} numerical '
                f'measure column(s) detected '
                f'automatically.'
            )
        })

    else:

        findings.append({
            'type': 'info',
            'text': (
                'No suitable numerical measure '
                'columns were detected.'
            )
        })

    # Identifier columns.
    if identifier_cols:

        findings.append({
            'type': 'info',
            'text': (
                'Identifier column(s) detected and '
                'excluded from numerical statistics: '
                + ', '.join(identifier_cols)
                + '.'
            )
        })

    # Duplicate identifier values are a separate issue from duplicate records.
    if identifier_duplicates:
        findings.append({
            'type': 'warn',
            'text': (
                'Duplicate identifier value(s) detected in: '
                + ', '.join(item['column'] for item in identifier_duplicates)
                + '.'
            )
        })
        for item in identifier_duplicates:
            details = '; '.join(
                f"{value['value']} appears {value['count']} times "
                f"(rows {_short_rows(value['row_numbers'], 6)})"
                for value in item['duplicate_values'][:5]
            )
            findings.append({
                'type': 'info',
                'text': f"{item['column']}: {details}."
            })

    # Potential identifier anomalies are reported separately from numeric outliers.
    if identifier_anomalies:
        findings.append({
            'type': 'warn',
            'text': (
                'Potential identifier pattern anomalies detected in: '
                + ', '.join(sorted({item['column'] for item in identifier_anomalies}))
                + '.'
            )
        })
        for item in identifier_anomalies:
            findings.append({
                'type': 'info',
                'text': item['message']
            })

    # Placeholder-like values: present in the data, not counted as missing.
    if placeholder_values:
        findings.append({
            'type': 'warn',
            'text': (
                'Placeholder-like value(s) (not counted as missing cells) '
                'detected in: '
                + ', '.join(item['column'] for item in placeholder_values)
                + '.'
            )
        })
        for item in placeholder_values:
            findings.append({
                'type': 'info',
                'text': item['message']
            })

    # Extreme values that stretch histograms.
    for item in extreme_skew:
        findings.append({
            'type': 'info',
            'text': f"{item['name']}: {item['note']}"
        })

    # Case/whitespace variants are a data-quality issue but the raw values stay unchanged.
    if text_inconsistencies:
        findings.append({
            'type': 'warn',
            'text': (
                'Case/whitespace inconsistencies detected in: '
                + ', '.join(item['column'] for item in text_inconsistencies)
                + '.'
            )
        })
        for item in text_inconsistencies:
            findings.append({
                'type': 'info',
                'text': item['message']
            })

    # Statistical outliers (IQR rule on valid numeric values; the same data
    # and rule as the box plots). Business-rule violations are separate.
    if outliers:

        findings.append({
            'type': 'warn',
            'text': (
                'Potential outliers detected in: '
                + ', '.join(
                    f"{x['name']} ({x['count']})"
                    for x in outliers
                )
                + ' (IQR rule on valid numeric values; same data and '
                'rule as the box plots).'
            )
        })

        for x in outliers:

            detail = (
                f"{x['name']}: {x['count']} statistical outlier(s) outside "
                f"{_number_text(x['lower_bound'])} to "
                f"{_number_text(x['upper_bound'])} "
                f"({x['low_count']} below, {x['high_count']} above; "
                f"{_rows_text(x['row_numbers'], 6)})"
            )

            if x['iqr_zero']:
                detail += (
                    '; IQR is 0 (most values are identical), so every '
                    'different value lies outside the bounds'
                )

            if x['also_business_rule_violations']:
                detail += (
                    f"; {x['also_business_rule_violations']} of them also "
                    f"violate the business rule"
                )

            findings.append({
                'type': 'info',
                'text': detail + '.'
            })

    else:

        if numeric_cols:

            findings.append({
                'type': 'good',
                'text': (
                    'No potential outliers detected '
                    'using the IQR method.'
                )
            })

    # Business-rule violations: data-quality rules, reported separately
    # from statistical outliers. Values are never changed or removed.
    if business_rules:

        violating = [b for b in business_rules if b['invalid_count']]

        if violating:

            findings.append({
                'type': 'warn',
                'text': (
                    'Business-rule violations detected in: '
                    + ', '.join(
                        f"{b['column']} (valid {b['rule_text']})"
                        for b in violating
                    )
                    + '.'
                )
            })

            for b in violating:
                findings.append({
                    'type': 'info',
                    'text': b['message']
                })

        else:

            findings.append({
                'type': 'good',
                'text': (
                    'All values satisfy the business rules: '
                    + ', '.join(
                        f"{b['column']} ({b['rule_text']})"
                        for b in business_rules
                    )
                    + '.'
                )
            })

        for b in business_rules:

            line = (
                f"{b['column']} (rule {b['rule_text']}): "
                f"{b['valid_count']} valid \u00b7 "
                f"{b['invalid_count']} invalid \u00b7 "
                f"{b['missing_count']} missing"
            )

            if b['non_numeric_count']:
                line += f" \u00b7 {b['non_numeric_count']} non-numeric"

            if b['invalid_count']:
                line += (
                    f"; {b['also_statistical_outliers']} violation(s) are "
                    f"also statistical outliers, "
                    f"{b['violations_not_statistical_outliers']} are not. "
                    f"Statistics are shown for raw numeric values and "
                    f"separately for valid values only"
                )

            findings.append({
                'type': 'info',
                'text': line + '.'
            })

    # Dates: valid, invalid and missing are separated. Invalid dates are
    # never used for the range or the time chart.
    for item in date_analysis:

        line = (
            f"{item['name']}: {item['valid_count']} valid \u00b7 "
            f"{item['invalid_count']} invalid \u00b7 "
            f"{item['missing_count']} missing date(s)."
        )

        if item['valid_count']:
            line += (
                f" Date range {item['min'][:10]} to {item['max'][:10]} "
                f"uses valid dates only."
            )

        if item['invalid_count']:
            line += (
                f" Invalid: {', '.join(item['invalid_examples'][:3])} "
                f"({_rows_text(item['invalid_row_numbers'], 6)})."
            )

        findings.append({
            'type': 'warn' if item['invalid_count'] else 'info',
            'text': line
        })

        if item['day_first_inferred']:

            findings.append({
                'type': 'info',
                'text': (
                    f"{item['name']}: numeric dates were read as "
                    f"day-first (dd/mm/yyyy) because the column contains "
                    f"dates whose first part is above 12."
                )
            })

    # Type inconsistencies.
    if inconsistent:

        findings.append({
            'type': 'warn',
            'text': (
                'Potential type inconsistencies '
                'detected in: '
                + ', '.join(
                    inconsistent
                )
                + '.'
            )
        })

        # Explain exactly which values caused each inconsistency.
        for item in inconsistent_details:

            findings.append({
                'type': 'info',
                'text': (
                    f"{item['name']}: "
                    f"{item['summary']}."
                )
            })

    else:

        findings.append({
            'type': 'good',
            'text': (
                'No major type inconsistencies detected.'
            )
        })

    # Constant columns.
    if constant_columns:

        findings.append({
            'type': 'info',
            'text': (
                'Constant column(s) detected: '
                + ', '.join(
                    constant_columns
                )
                + '.'
            )
        })

    # High-cardinality columns.
    if high_cardinality_columns:

        findings.append({
            'type': 'info',
            'text': (
                'High-cardinality / free-text column(s) '
                'detected; no frequency chart is drawn '
                'for them or only the top categories '
                'are shown: '
                + ', '.join(
                    high_cardinality_columns
                )
                + '.'
            )
        })

    # Date columns.
    if date_cols:

        findings.append({
            'type': 'info',
            'text': (
                f'{len(date_cols)} date/time '
                f'column(s) detected automatically.'
            )
        })

    # ---------------------------------------------------------
    # DATA PREVIEW
    # ---------------------------------------------------------

    preview = df.copy()

    preview = preview.where(
        pd.notna(preview),
        None
    )

    preview_source_rows = source_row_numbers(df)[:len(preview)]
    preview_rows = []
    for offset, row in enumerate(preview.to_dict(orient='records')):
        item = {
            str(k): clean_scalar(v)
            for k, v in row.items()
        }
        item['__source_row_number'] = int(preview_source_rows[offset])
        preview_rows.append(item)

    # ---------------------------------------------------------
    # AFFECTED RECORDS FOR MISSING VALUES & DUPLICATES
    # ---------------------------------------------------------

    missing_row_mask = df.isna().any(
        axis=1
    )

    missing_records = build_issue_records(
        df,
        missing_row_mask,
        include_missing_columns=True
    )

    duplicate_records = build_issue_records(
        df,
        duplicate_row_mask
    )

    # Duplicate groups were already built from the semantic duplicate key.

    # ---------------------------------------------------------
    # FINAL RESPONSE
    # ---------------------------------------------------------

    return {

        'summary': {

            'rows': int(rows),

            'columns': int(cols),

            'missing_cells': int(
                missing_series.sum()
            ),

            'missing_percent': (
                float(
                    missing_series.sum()
                    / (rows * cols)
                    * 100
                )
                if rows and cols
                else 0
            ),

            # Exact duplicates (every column identical).
            'duplicate_rows': duplicate_count,

            'duplicate_percent': (
                float(
                    duplicate_count
                    / rows
                    * 100
                )
                if rows
                else 0
            ),

            'exact_duplicate_groups': duplicate_analysis['exact_duplicate_groups'],

            # Repeated records when identifier columns are ignored
            # (includes the exact duplicates).
            'duplicate_rows_ignoring_identifiers': duplicates_ignoring_identifiers,

            'duplicate_percent_ignoring_identifiers': (
                float(duplicates_ignoring_identifiers / rows * 100)
                if rows
                else 0
            ),

            'duplicate_groups_total': duplicate_analysis['duplicate_groups_total'],

            # Additional duplicates found ONLY by ignoring identifier
            # columns (excludes the exact duplicates above):
            #   duplicate_rows + additional... = duplicate_rows_ignoring_identifiers
            'additional_duplicate_rows_ignoring_identifiers': (
                duplicate_analysis['additional_duplicate_rows_ignoring_identifiers']
            ),

            'additional_duplicate_percent_ignoring_identifiers': (
                float(
                    duplicate_analysis['additional_duplicate_rows_ignoring_identifiers']
                    / rows * 100
                )
                if rows
                else 0
            ),

            'identifier_only_duplicate_groups': (
                duplicate_analysis['identifier_only_duplicate_groups']
            ),

            'duplicate_ignored_identifier_columns': (
                duplicate_analysis['ignored_identifier_columns']
            )
        },

        'columns': columns,

        'statistics': stats,

        'missing': missing,

        'charts': charts,

        'preview': {
            'columns': [
                str(c)
                for c in df.columns
            ],
            'rows': preview_rows
        },

        'issue_records': {
            'missing': missing_records,
            'duplicates': duplicate_records
        },

        'duplicate_groups': duplicate_groups,

        'business_rules': business_rules,

        'identifier_duplicates': identifier_duplicates,
        'identifier_anomalies': identifier_anomalies,
        'text_inconsistencies': text_inconsistencies,
        'placeholder_values': placeholder_values,

        # New universal profiling information.
        'profile': {
            'numerical_columns': numeric_cols,
            'categorical_columns': categorical_cols,
            'text_columns': text_cols,
            'date_columns': date_cols,
            'identifier_columns': identifier_cols,
            'constant_columns': constant_columns,
            'high_cardinality_columns': (
                high_cardinality_columns
            ),
            'identifier_duplicates': identifier_duplicates,
            'identifier_anomalies': identifier_anomalies,
            'text_inconsistencies': text_inconsistencies
        },

        'date_analysis': date_analysis,

        'type_inconsistencies': (
            inconsistent_details
        ),

        'quality': {
            'major_issues': len([
                f
                for f in findings
                if f['type'] == 'warn'
            ]),
            'findings': findings
        },

        'report': {
            'outliers': outliers,
            'business_rules': business_rules,
            'inconsistent_columns': inconsistent,
            'inconsistent_details': (
                inconsistent_details
            ),
            'identifier_columns': (
                identifier_cols
            ),
            'constant_columns': (
                constant_columns
            ),
            'high_cardinality_columns': (
                high_cardinality_columns
            ),
            'date_analysis': date_analysis,
            'identifier_duplicates': identifier_duplicates,
            'identifier_anomalies': identifier_anomalies,
            'text_inconsistencies': text_inconsistencies,
            'placeholder_values': placeholder_values,
            'extreme_skew': extreme_skew
        }
    }
