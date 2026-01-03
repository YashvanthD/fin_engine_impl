from fin_server.repository.mongo_helper import init_repositories, get_collection
from fin_server.utils.helpers import normalize_doc




def is_empty(v):
    return v is None or (isinstance(v, str) and str(v).strip() == '')


def coerce_number(v):
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return v
        return float(v) if ('.' in str(v) or 'e' in str(v).lower()) else int(float(v))
    except Exception:
        return v


def normalize_sampling_docs(limit=None):
    """Normalize sampling documents in place.

    Returns count of updated documents.
    """
    coll = get_collection('sampling', create_if_missing=True)
    query = {}
    cursor = coll.find(query).limit(limit) if limit else coll.find(query)
    updated = 0
    for doc in cursor:
        d = normalize_doc(doc)
        set_ops = {}
        unset_ops = {}

        alias_map = {
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

        for alias_key, canon_key in alias_map.items():
            if alias_key in doc and not is_empty(doc.get(alias_key)):
                if canon_key not in doc or is_empty(doc.get(canon_key)):
                    val = doc.get(alias_key)
                    if canon_key in ('total_cost', 'total_count'):
                        val = coerce_number(val)
                    set_ops[canon_key] = val
                unset_ops[alias_key] = ''

        # Remove duplicates of common totals and aliases
        for dup in ('totalAmount', 'total_amount', 'totalCount'):
            if dup in doc:
                unset_ops[dup] = ''

        core_aliases = ['pondId', 'samplingDate', 'sampleSize', 'averageWeight', 'averageLength', 'recordedBy', 'costUnit', 'totalAmount', 'total_amount', 'totalCount']
        for k in core_aliases:
            if k in doc:
                unset_ops[k] = ''

        if set_ops or unset_ops:
            update = {}
            if set_ops:
                update['$set'] = set_ops
            if unset_ops:
                update['$unset'] = {k: '' for k in unset_ops.keys()}
            try:
                coll.update_one({'_id': doc.get('_id')}, update)
                updated += 1
            except Exception:
                # best-effort: ignore failures for now
                continue
    return updated


if __name__ == '__main__':
    n = normalize_sampling_docs()
    print(f"Normalized {n} sampling documents")
