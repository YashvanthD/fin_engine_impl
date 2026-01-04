import logging
from typing import Any, Dict, Optional

from fin_server.repository.mongo_helper import get_collection

logger = logging.getLogger(__name__)


def atomic_update_pond_metadata(pond_repo: Any, pond_id: str, inc_fields: Dict[str, int] = None, set_fields: Dict[str, Any] = None, unset_fields: Dict[str, Any] = None) -> Any:
    try:
        if pond_repo is None:
            raise RuntimeError('No pond_repo provided')
        return pond_repo.atomic_update_metadata(pond_id, inc_fields=inc_fields, set_fields=set_fields, unset_fields=unset_fields)
    except Exception:
        logger.exception('Failed to atomic update pond metadata')
        raise


def create_pond_event(pond_event_repo: Any, pond_id: str, species: str, count: int, recorded_by: str, details: Dict[str, Any] = None) -> Any:
    details = details or {}
    ev = {'pond_id': pond_id, 'event_type': 'buy', 'details': details, 'recorded_by': recorded_by}
    try:
        if hasattr(pond_event_repo, 'create'):
            return pond_event_repo.create(ev)
        if hasattr(pond_event_repo, 'insert_one'):
            return pond_event_repo.insert_one(ev)
    except Exception:
        logger.exception('Failed to create pond_event')
        raise
    return None


# New: delete pond and cascade-delete related datasets (sampling, events, activity, analytics, expenses)
def delete_pond_and_related(
    pond_id: str,
    pond_collection_name: str = 'pond',
    sampling_collection: str = 'sampling',
    pond_event_collection: str = 'pond_event',
    fish_activity_collection: str = 'fish_activity',
    fish_analytics_collection: str = 'fish_analytics',
    expenses_collection: str = 'expenses',
) -> Dict[str, Optional[int]]:
    """Delete a pond and related documents using repository singletons from get_collection().

    This simplified implementation assumes `get_collection()` always returns a valid
    repository object and directly calls the underlying collection APIs. No client or
    transaction logic is used.
    """
    summary: Dict[str, Optional[int]] = {
        'pond_deleted': None,
        'sampling_deleted': None,
        'pond_events_deleted': None,
        'fish_activity_deleted': None,
        'fish_analytics_deleted': None,
        'expenses_deleted': None,
    }

    def _get_repo(name: str):
        # Per your instruction, assume this always returns a valid repo
        return get_collection(name)

    def _coll_from(repo_obj, repo_name: Optional[str] = None):
        # prefer repository.collection or .coll if present, else try repo_obj.db[repo_name], else return repo_obj
        if hasattr(repo_obj, 'collection') and getattr(repo_obj, 'collection') is not None:
            return getattr(repo_obj, 'collection')
        if hasattr(repo_obj, 'coll') and getattr(repo_obj, 'coll') is not None:
            return getattr(repo_obj, 'coll')
        # If repo object exposes a db attribute, use it to fetch named collection
        if hasattr(repo_obj, 'db') and repo_name:
            try:
                return repo_obj.db[repo_name]
            except Exception:
                pass
        return repo_obj

    def _delete_many(repo_name: str, query: Dict[str, Any]) -> Optional[int]:
        repo_obj = _get_repo(repo_name)
        coll = _coll_from(repo_obj, repo_name)
        res = coll.delete_many(query)
        return getattr(res, 'deleted_count', None)

    def _delete_one(repo_name: str, query: Dict[str, Any]) -> Optional[int]:
        repo_obj = _get_repo(repo_name)
        coll = _coll_from(repo_obj, repo_name)
        res = coll.delete_one(query)
        return getattr(res, 'deleted_count', None)

    # Perform deletions (straightforward, no try/excepts around get_collection)
    summary['sampling_deleted'] = _delete_many(sampling_collection, {'pond_id': pond_id})
    summary['pond_events_deleted'] = _delete_many(pond_event_collection, {'pond_id': pond_id})
    summary['fish_activity_deleted'] = _delete_many(fish_activity_collection, {'pond_id': pond_id})
    summary['fish_analytics_deleted'] = _delete_many(fish_analytics_collection, {'pond_id': pond_id})
    summary['expenses_deleted'] = _delete_many(expenses_collection, {'pond_id': pond_id})

    # Delete the pond doc (try by pond_id then by _id)
    deleted = _delete_one(pond_collection_name, {'pond_id': pond_id})
    if not deleted:
        deleted = _delete_one(pond_collection_name, {'_id': pond_id})
    summary['pond_deleted'] = deleted

    return summary
