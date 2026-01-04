import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def upsert_fish_stock(fish_repo: Any, species: str, account_key: str, count: int, common_name: Optional[str] = None) -> Optional[Any]:
    """Update existing fish current_stock or create a minimal fish doc.

    Returns the fish _id or None.
    """
    try:
        if fish_repo is None:
            raise RuntimeError('No fish_repo provided')
        existing = None
        if hasattr(fish_repo, 'find_one'):
            existing = fish_repo.find_one({'$or': [{'species_code': species}, {'_id': species}]})
        if existing:
            if hasattr(fish_repo, 'update'):
                fish_repo.update({'_id': existing.get('_id')}, {'current_stock': (existing.get('current_stock', 0) or 0) + int(count)})
            else:
                fish_repo.update_one({'_id': existing.get('_id')}, {'$inc': {'current_stock': int(count)}})
            return existing.get('_id')
        # create minimal fish doc
        fish_doc = {'_id': species, 'species_code': species, 'common_name': common_name or species, 'current_stock': int(count), 'account_key': account_key}
        if hasattr(fish_repo, 'create'):
            return fish_repo.create(fish_doc)
        if hasattr(fish_repo, 'insert_one'):
            res = fish_repo.insert_one(fish_doc)
            return getattr(res, 'inserted_id', None)
    except Exception:
        logger.exception('Failed to upsert fish stock')
        raise
    return None

