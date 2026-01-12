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
    fish_collection: str = 'fish',
) -> Dict[str, Optional[int]]:
    """Delete a pond and related documents using repository singletons from get_collection().

    This implementation:
    1. Loads pond metadata to get fish counts by species
    2. Decrements fish.current_stock for each species
    3. Deletes all related documents (sampling, events, etc.)
    4. Deletes the pond
    """
    summary: Dict[str, Optional[int]] = {
        'pond_deleted': None,
        'sampling_deleted': None,
        'pond_events_deleted': None,
        'fish_activity_deleted': None,
        'fish_analytics_deleted': None,
        'expenses_deleted': None,
        'fish_stock_updated': None,
    }

    def _get_repo(name: str):
        return get_collection(name)

    def _coll_from(repo_obj, repo_name: Optional[str] = None):
        if hasattr(repo_obj, 'collection') and getattr(repo_obj, 'collection') is not None:
            return getattr(repo_obj, 'collection')
        if hasattr(repo_obj, 'coll') and getattr(repo_obj, 'coll') is not None:
            return getattr(repo_obj, 'coll')
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

    # Step 0: Load pond to get fish counts by species
    try:
        pond_repo = _get_repo(pond_collection_name)
        pond_coll = _coll_from(pond_repo, pond_collection_name)
        pond = pond_coll.find_one({'pond_id': pond_id}) or pond_coll.find_one({'_id': pond_id})

        if pond:
            # Get fish_types from metadata: { "TILAPIA": 500, "CATLA": 300 }
            fish_types = (pond.get('metadata') or {}).get('fish_types', {})

            if fish_types:
                fish_repo = _get_repo(fish_collection)
                fish_coll = _coll_from(fish_repo, fish_collection)

                fish_updated_count = 0
                for species, count in fish_types.items():
                    if count and int(count) > 0:
                        try:
                            # Decrement current_stock for this species
                            result = fish_coll.update_one(
                                {'$or': [{'_id': species}, {'species_code': species}]},
                                {'$inc': {'current_stock': -int(count)}}
                            )
                            if result.modified_count > 0:
                                fish_updated_count += 1
                                logger.info(f'Decremented fish {species} current_stock by {count} (pond {pond_id} deletion)')
                        except Exception:
                            logger.exception(f'Failed to decrement fish {species} stock for pond deletion')

                summary['fish_stock_updated'] = fish_updated_count
    except Exception:
        logger.exception('Error loading pond for fish stock update during deletion')

    # Perform deletions
    summary['sampling_deleted'] = _delete_many(sampling_collection, {'pond_id': pond_id})
    summary['pond_events_deleted'] = _delete_many(pond_event_collection, {'pond_id': pond_id})
    summary['fish_activity_deleted'] = _delete_many(fish_activity_collection, {'pond_id': pond_id})
    summary['fish_analytics_deleted'] = _delete_many(fish_analytics_collection, {'pond_id': pond_id})
    summary['expenses_deleted'] = _delete_many(expenses_collection, {'$or': [{'pond_id': pond_id}, {'metadata.pond_id': pond_id}]})

    # Delete the pond doc (try by pond_id then by _id)
    deleted = _delete_one(pond_collection_name, {'pond_id': pond_id})
    if not deleted:
        deleted = _delete_one(pond_collection_name, {'_id': pond_id})
    summary['pond_deleted'] = deleted

    return summary
