import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def record_fish_activity(activity_repo: Any, account_key: str, pond_id: str, species: str, event_type: str, count: int, user_key: str, details: Dict[str, Any] = None) -> Any:
    doc = {'account_key': account_key, 'pond_id': pond_id, 'fish_id': species, 'event_type': event_type, 'count': count, 'details': details or {}, 'user_key': user_key}
    try:
        if activity_repo is None:
            raise RuntimeError('No activity_repo provided')
        if hasattr(activity_repo, 'create'):
            return activity_repo.create(doc)
        if hasattr(activity_repo, 'insert_one'):
            return activity_repo.insert_one(doc)
    except Exception:
        logger.exception('Failed to create fish activity')
        raise
    return None

