from typing import Any, Dict, Iterable, List, Tuple
import re


# Canonical alias map for sampling-related fields
SAMPLING_ALIAS_MAP = {
    'pondId': 'pond_id',
    'samplingDate': 'sampling_date',
    'sampleSize': 'sample_size',
    'averageWeight': 'average_weight',
    'averageLength': 'average_length',
    'survivalRate': 'survival_rate',
    'feedConversionRatio': 'feed_conversion_ratio',
    'recordedBy': 'recorded_by',
    'totalAmount': 'total_cost',
    'total_amount': 'total_cost',
    'totalCount': 'total_count',
    'total_count': 'total_count',
    'costUnit': 'cost_unit',
    'cost_unit': 'cost_unit',
}


def is_empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and str(v).strip() == '')


def coerce_number(v: Any) -> Any:
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return v
        s = str(v)
        # treat scientific or float-like strings as float, otherwise int when possible
        if '.' in s or 'e' in s.lower():
            return float(s)
        return int(float(s))
    except Exception:
        return v


def first_present(d: Dict[str, Any], keys: Iterable[str]) -> Any:
    """Return the first non-empty value for the provided keys in the dict."""
    for k in keys:
        if k in d and not is_empty(d.get(k)):
            return d.get(k)
    return None


def extract_alias_set_unset(doc: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Given a document, return (set_ops, unset_keys).

    set_ops is a mapping of canonical field -> value (coerced where appropriate).
    unset_keys is a list of alias keys to remove after normalization.
    """
    set_ops: Dict[str, Any] = {}
    unset_keys: List[str] = []

    for alias_key, canon_key in SAMPLING_ALIAS_MAP.items():
        if alias_key in doc and not is_empty(doc.get(alias_key)):
            # Only set canonical key when canonical absent or empty
            if canon_key not in doc or is_empty(doc.get(canon_key)):
                val = doc.get(alias_key)
                if canon_key in ('total_cost', 'total_count'):
                    val = coerce_number(val)
                set_ops[canon_key] = val
            unset_keys.append(alias_key)

    # Remove duplicate common alias keys
    for dup in ('totalAmount', 'total_amount', 'totalCount'):
        if dup in doc and dup not in unset_keys:
            unset_keys.append(dup)

    return set_ops, unset_keys


# --- New generic normalization helpers ---

_camel_re1 = re.compile('(.)([A-Z][a-z]+)')
_camel_re2 = re.compile('([a-z0-9])([A-Z])')


def camel_to_snake(name: str) -> str:
    """Convert a camelCase or PascalCase string to snake_case."""
    if not name or '_' in name:
        return name
    s1 = _camel_re1.sub(r'\1_\2', name)
    snake = _camel_re2.sub(r'\1_\2', s1).lower()
    return snake


def normalize_keys(obj: Any, alias_map: Dict[str, str] = None, recurse: bool = True) -> Any:
    """Recursively normalize dict keys:

    - If alias_map is provided and a key exists in it, use its mapped canonical key.
    - Otherwise convert camelCase keys to snake_case using `camel_to_snake`.
    - For nested dicts/lists, recurse when recurse=True.

    Returns a new object (does not mutate input).
    """
    if alias_map is None:
        alias_map = {}

    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            # preserve special keys like '_id' unchanged
            if k.startswith('_'):
                new_key = k
            elif k in alias_map:
                new_key = alias_map[k]
            else:
                new_key = camel_to_snake(k)
            # Recurse into values
            if recurse:
                new_val = normalize_keys(v, alias_map=alias_map, recurse=recurse)
            else:
                new_val = v
            # If key collision occurs, prefer existing value (do not overwrite)
            if new_key in out:
                # If both values are dicts, merge shallowly
                if isinstance(out[new_key], dict) and isinstance(new_val, dict):
                    merged = out[new_key].copy()
                    merged.update(new_val)
                    out[new_key] = merged
                else:
                    # keep existing value; do not overwrite
                    pass
            else:
                out[new_key] = new_val
        return out
    elif isinstance(obj, list):
        return [normalize_keys(i, alias_map=alias_map, recurse=recurse) for i in obj]
    else:
        return obj


def normalize_document_fields(doc: Dict[str, Any], alias_map: Dict[str, str] = None) -> Dict[str, Any]:
    """Convenience wrapper: normalize a single document's keys using an alias map merged with SAMPLING_ALIAS_MAP."""
    # Merge provided alias map with default sampling map (user can override keys)
    merged_map = SAMPLING_ALIAS_MAP.copy()
    if alias_map:
        merged_map.update(alias_map)
    return normalize_keys(doc, alias_map=merged_map)


__all__ = [
    'SAMPLING_ALIAS_MAP', 'is_empty', 'coerce_number', 'first_present', 'extract_alias_set_unset',
    'camel_to_snake', 'normalize_keys', 'normalize_document_fields'
]
