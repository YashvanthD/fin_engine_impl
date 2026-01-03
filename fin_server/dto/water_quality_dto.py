from typing import Optional, Dict, Any, List
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc
import zoneinfo
from fin_server.utils.time_utils import get_time_date_dt, now_std


class WaterQualityRecordDTO:
    def __init__(self, id: Optional[str], pondId: str, timestamp: Optional[str], parameters: Dict[str, Any],
                 recordedBy: Optional[str], notes: Optional[str] = None, alerts: Optional[List[Dict[str, Any]]] = None, extra: Dict[str, Any] = None):
        self.id = id
        self.pondId = pondId
        self.timestamp = _to_iso_if_epoch(timestamp) if timestamp is not None else None
        self.parameters = parameters or {}
        self.recordedBy = recordedBy
        self.notes = notes
        self.alerts = alerts or []
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            pondId=d.get('pondId') or d.get('pond_id') or d.get('pond'),
            timestamp=d.get('timestamp') or d.get('recorded_at') or d.get('created_at'),
            parameters=d.get('parameters') or d.get('params') or d.get('parameters', {}),
            recordedBy=d.get('recordedBy') or d.get('recorded_by') or d.get('recorded_by_user') or d.get('user_key'),
            notes=d.get('notes') or d.get('remark'),
            alerts=d.get('alerts') or [],
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id') or payload.get('_id'),
            pondId=payload.get('pondId') or payload.get('pond_id') or payload.get('pond'),
            timestamp=payload.get('timestamp') or payload.get('recorded_at') or payload.get('created_at'),
            parameters=payload.get('parameters') or payload.get('params') or {},
            recordedBy=payload.get('recordedBy') or payload.get('recorded_by') or payload.get('user_key'),
            notes=payload.get('notes') or payload.get('remark'),
            alerts=payload.get('alerts') or [],
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'pondId': self.pondId,
            'timestamp': self.timestamp,
            'parameters': self.parameters,
            'recordedBy': self.recordedBy,
            'notes': self.notes,
            'alerts': self.alerts,
            **self.extra
        }

    def to_db_doc(self) -> Dict[str, Any]:
        doc = {
            'pond_id': self.pondId,
            'timestamp': self.timestamp,
            'parameters': self.parameters,
            'recorded_by': self.recordedBy,
            'notes': self.notes,
            'alerts': self.alerts
        }
        for k, v in (self.extra or {}).items():
            if k not in doc:
                doc[k] = v
        return doc

    def save(self, collection=None, repo=None, collection_name: Optional[str] = 'water_quality', upsert: bool = False):
        doc = self.to_db_doc()
        if 'created_at' not in doc:
            ist = zoneinfo.ZoneInfo('Asia/Kolkata')
            doc['created_at'] = now_std(include_time=True)
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
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        if upsert and doc.get('_id'):
            return coll.replace_one({'_id': doc['_id']}, doc, upsert=True)
        return coll.insert_one(doc)

    def update(self, filter_query: Dict[str, Any], update_fields: Dict[str, Any], collection=None, repo=None, collection_name: Optional[str] = 'water_quality'):
        if repo is not None and hasattr(repo, 'update'):
            return repo.update(filter_query, update_fields)
        if collection is None and repo is not None and hasattr(repo, 'get_collection'):
            collection = repo.get_collection(collection_name)
        if collection is not None:
            return collection.update_one(filter_query, {'$set': update_fields})
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        return coll.update_one(filter_query, {'$set': update_fields})
