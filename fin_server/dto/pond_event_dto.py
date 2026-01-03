from typing import Optional, Dict, Any
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc
from fin_server.repository.mongo_helper import get_collection




class PondEventDTO:
    def __init__(self, id: Optional[str], pondId: str, eventType: str, timestamp: Optional[str], species: Optional[str],
                 count: Optional[int], details: Optional[Dict[str, Any]] = None, recordedBy: Optional[str] = None, extra: Dict[str, Any] = None):
        self.id = id
        self.pondId = pondId
        self.eventType = eventType
        self.timestamp = _to_iso_if_epoch(timestamp) if timestamp is not None else None
        self.species = species
        self.count = int(count) if count is not None else None
        self.details = details or {}
        self.recordedBy = recordedBy
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            pondId=d.get('pondId') or d.get('pond_id') or d.get('pond'),
            eventType=d.get('eventType') or d.get('event_type') or d.get('type'),
            timestamp=d.get('timestamp') or d.get('created_at'),
            species=d.get('species') or d.get('species_code') or d.get('fish_id'),
            count=d.get('count'),
            details=d.get('details') or {},
            recordedBy=d.get('recordedBy') or d.get('recorded_by'),
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id') or payload.get('_id'),
            pondId=payload.get('pondId') or payload.get('pond_id') or payload.get('pond'),
            eventType=payload.get('eventType') or payload.get('event_type') or payload.get('type'),
            timestamp=payload.get('timestamp') or payload.get('created_at'),
            species=payload.get('species') or payload.get('species_code') or payload.get('fish_id'),
            count=payload.get('count'),
            details=payload.get('details') or payload.get('data') or {},
            recordedBy=payload.get('recordedBy') or payload.get('recorded_by'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'pondId': self.pondId,
            'eventType': self.eventType,
            'timestamp': self.timestamp,
            'species': self.species,
            'count': self.count,
            'details': self.details,
            'recordedBy': self.recordedBy,
            **self.extra
        }

    def to_db_doc(self) -> Dict[str, Any]:
        doc = {
            'pond_id': self.pondId,
            'event_type': self.eventType,
            'fish_id': self.species,
            'count': self.count,
            'details': self.details,
            'user_key': self.recordedBy
        }
        for k, v in (self.extra or {}).items():
            if k not in doc:
                doc[k] = v
        return doc

    def save(self, collection=None, repo=None, collection_name: Optional[str] = 'pond_events', upsert: bool = False):
        doc = self.to_db_doc()
        from fin_server.utils.time_utils import get_time_date_dt
        if 'created_at' not in doc:
            doc['created_at'] = get_time_date_dt(include_time=True)
        if repo is not None:
            try:
                if hasattr(repo, 'create'):
                    return repo.create(doc)
            except Exception:
                pass
            try:
                coll = repo.get_collection(collection_name)
                if coll:
                    if upsert and doc.get('_id'):
                        return coll.replace_one({'_id': doc['_id']}, doc, upsert=True)
                    return coll.insert_one(doc)
            except Exception:
                pass
        if collection is not None:
            if upsert and doc.get('_id'):
                return collection.replace_one({'_id': doc['_id']}, doc, upsert=True)
            return collection.insert_one(doc)
        coll = get_collection(collection_name)
        if upsert and doc.get('_id'):
            return coll.replace_one({'_id': doc['_id']}, doc, upsert=True)
        return coll.insert_one(doc)

    def update(self, filter_query: Dict[str, Any], update_fields: Dict[str, Any], collection=None, repo=None, collection_name: Optional[str] = 'pond_events'):
        if repo is not None and hasattr(repo, 'update'):
            return repo.update(filter_query, update_fields)
        if collection is None and repo is not None and hasattr(repo, 'get_collection'):
            collection = repo.get_collection(collection_name)
        if collection is not None:
            return collection.update_one(filter_query, {'$set': update_fields})
        coll = get_collection(collection_name)
        return coll.update_one(filter_query, {'$set': update_fields})
