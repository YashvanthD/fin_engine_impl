from typing import Optional, Dict, Any

from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc
from fin_server.utils.time_utils import get_time_date_dt




class FeedingRecordDTO:
    def __init__(self, id: Optional[str], pondId: str, feedType: str, quantity: float,
                 feedingTime: Optional[str], waterTemperature: Optional[float], fishBehavior: Optional[str],
                 recordedBy: Optional[str], notes: Optional[str], extra: Dict[str, Any] = None):
        self.id = id
        self.pondId = pondId
        self.feedType = feedType
        self.quantity = float(quantity) if quantity is not None else 0.0
        self.feedingTime = _to_iso_if_epoch(feedingTime) if feedingTime is not None else None
        self.waterTemperature = float(waterTemperature) if waterTemperature is not None else None
        self.fishBehavior = fishBehavior
        self.recordedBy = recordedBy
        self.notes = notes
        self.extra = extra or {}
        # default collection (use manager helper)
        try:
            self.coll = get_collection('feeding')
        except Exception:
            self.coll = None

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            pondId=d.get('pondId') or d.get('pond_id') or d.get('pond'),
            feedType=d.get('feedType') or d.get('feed_type') or d.get('feed'),
            quantity=d.get('quantity') or d.get('feedQuantity') or d.get('feed_quantity') or 0,
            feedingTime=d.get('feedingTime') or d.get('date'),
            waterTemperature=d.get('waterTemperature') or d.get('water_temperature'),
            fishBehavior=d.get('fishBehavior') or d.get('fish_behavior'),
            recordedBy=d.get('recordedBy') or d.get('recorded_by'),
            notes=d.get('notes') or d.get('remark') or d.get('remarks'),
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id') or payload.get('_id'),
            pondId=payload.get('pondId') or payload.get('pond_id') or payload.get('pond'),
            feedType=payload.get('feedType') or payload.get('feed_type') or payload.get('feed'),
            quantity=payload.get('quantity') or payload.get('feedQuantity') or payload.get('feed_quantity') or 0,
            feedingTime=payload.get('feedingTime') or payload.get('date'),
            waterTemperature=payload.get('waterTemperature') or payload.get('water_temperature'),
            fishBehavior=payload.get('fishBehavior') or payload.get('fish_behavior'),
            recordedBy=payload.get('recordedBy') or payload.get('recorded_by'),
            notes=payload.get('notes') or payload.get('remark') or payload.get('remarks'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'pondId': self.pondId,
            'feedType': self.feedType,
            'quantity': self.quantity,
            'feedingTime': self.feedingTime,
            'waterTemperature': self.waterTemperature,
            'fishBehavior': self.fishBehavior,
            'recordedBy': self.recordedBy,
            'notes': self.notes,
            **self.extra
        }

    def to_db_doc(self) -> Dict[str, Any]:
        # Map to DB field names (snake_case where repository expects)
        doc = {
            'pond_id': self.pondId,
            'feed_type': self.feedType,
            'quantity': self.quantity,
            'feeding_time': self.feedingTime,
            'water_temperature': self.waterTemperature,
            'fish_behavior': self.fishBehavior,
            'recorded_by': self.recordedBy,
            'notes': self.notes
        }
        # merge extras (but don't overwrite core fields)
        for k, v in (self.extra or {}).items():
            if k not in doc:
                doc[k] = v
        return doc

    def save(self, collection=None, repo=None, collection_name: Optional[str] = None, upsert: bool = False):
        """Persist the feeding record. Accepts either a pymongo collection or a repo object. Returns insert result."""
        doc = self.to_db_doc()
        # Add created_at if not present
        if 'created_at' not in doc:
            doc['created_at'] = get_time_date_dt(include_time=True)
        # If repo provided
        if repo is not None:
            # try repository create method
            try:
                if hasattr(repo, 'create'):
                    return repo.create(doc)
            except Exception:
                pass
            # try get_collection
            try:
                coll = repo.get_collection(collection_name) if collection_name else None
                if coll:
                    res = coll.insert_one(doc) if not upsert else coll.update_one({'_id': doc.get('_id')} if doc.get('_id') else doc, {'$set': doc}, upsert=True)
                    return res
            except Exception:
                pass
        # if collection provided directly
        if collection is not None:
            if upsert and doc.get('_id'):
                return collection.update_one({'_id': doc.get('_id')}, {'$set': doc}, upsert=True)
            return collection.insert_one(doc)
        # fallback: try to get collection from singleton
        try:
            if upsert and doc.get('_id'):
                return self.coll.update_one({'_id': doc.get('_id')}, {'$set': doc}, upsert=True)
            return self.coll.insert_one(doc)
        except Exception as e:
            raise

    def update(self, filter_query: Dict[str, Any], update_fields: Dict[str, Any], collection=None, repo=None, collection_name: Optional[str] = None):
        try:
            if repo is not None and hasattr(repo, 'update'):
                return repo.update(filter_query, update_fields)
            if collection is None and repo is not None and hasattr(repo, 'get_collection'):
                collection = repo.get_collection(collection_name)
            if collection is not None:
                return collection.update_one(filter_query, {'$set': update_fields})
            # fallback to module helper
            coll = get_collection(collection_name or 'feeding')
            return coll.update_one(filter_query, {'$set': update_fields})
        except Exception:
            raise
