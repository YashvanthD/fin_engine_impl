import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def add_analytics_batch(fa_repo: Any, species: str, count: int, fish_age: int, account_key: str, event_id: str, pond_id: str, fish_weight: Optional[float] = None) -> None:
    try:
        if fa_repo is None:
            raise RuntimeError('No fish analytics repo provided')
        if hasattr(fa_repo, 'add_batch'):
            fa_repo.add_batch(species, int(count), int(fish_age or 0), account_key=account_key, event_id=event_id, fish_weight=fish_weight, pond_id=pond_id)
        else:
            # fallback: insert into fish_analytics collection if available
            if hasattr(fa_repo, 'insert_one'):
                doc = {'species_id': species, 'count': int(count), 'fish_age_in_month': int(fish_age or 0), 'date_added': None, 'account_key': account_key, 'pond_id': pond_id}
                if fish_weight is not None:
                    doc['fish_weight'] = fish_weight
                try:
                    fa_repo.insert_one(doc)
                except Exception:
                    logger.exception('Failed to insert analytics batch')
    except Exception:
        logger.exception('Failed to add analytics batch')
        raise

