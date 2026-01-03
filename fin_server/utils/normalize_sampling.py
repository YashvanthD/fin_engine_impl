from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.helpers import normalize_doc
from fin_server.utils.normalizers import extract_alias_set_unset




def normalize_sampling_docs(limit=None):
    """Normalize sampling documents in place using shared normalizers.

    Returns count of updated documents.
    """
    coll = get_collection('sampling')
    query = {}
    cursor = coll.find(query).limit(limit) if limit else coll.find(query)
    updated = 0
    for doc in cursor:
        d = normalize_doc(doc)
        set_ops, unset_keys = extract_alias_set_unset(doc)

        if set_ops or unset_keys:
            update = {}
            if set_ops:
                update['$set'] = set_ops
            if unset_keys:
                update['$unset'] = {k: '' for k in unset_keys}
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
