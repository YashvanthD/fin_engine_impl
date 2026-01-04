import logging
from typing import Any, Dict, Optional

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

