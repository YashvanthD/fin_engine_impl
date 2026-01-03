from typing import Optional, Dict, Any
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc


class FishDTO:
    def __init__(self, id: Optional[str], species_code: str, common_name: Optional[str] = None,
                 scientific_name: Optional[str] = None, createdAt: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None, extra: Dict[str, Any] = None):
        self.id = id
        self.species_code = species_code
        self.common_name = common_name
        self.scientific_name = scientific_name
        self.createdAt = _to_iso_if_epoch(createdAt) if createdAt is not None else None
        self.metadata = metadata or {}
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        species = d.get('_id') or d.get('species_code') or d.get('id')
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            species_code=d.get('species_code') or species,
            common_name=d.get('common_name') or d.get('commonName'),
            scientific_name=d.get('scientific_name') or d.get('scientificName'),
            createdAt=d.get('created_at') or d.get('createdAt'),
            metadata=d.get('metadata') or {},
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id') or payload.get('_id'),
            species_code=payload.get('species_code') or payload.get('speciesCode') or payload.get('species'),
            common_name=payload.get('common_name') or payload.get('commonName') or payload.get('common'),
            scientific_name=payload.get('scientific_name') or payload.get('scientificName'),
            createdAt=payload.get('createdAt') or payload.get('created_at'),
            metadata=payload.get('metadata') or {},
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            '_id': self.id or self.species_code,
            'species_code': self.species_code,
            'common_name': self.common_name,
            'scientific_name': self.scientific_name,
            'created_at': self.createdAt,
            'metadata': self.metadata,
            **self.extra
        }

    def to_ui(self) -> Dict[str, Any]:
        # UI-friendly shape
        return {
            'id': self.id or self.species_code,
            'speciesCode': self.species_code,
            'commonName': self.common_name,
            'scientificName': self.scientific_name,
            'createdAt': self.createdAt,
            'metadata': self.metadata,
            **self.extra
        }

    def to_db_doc(self) -> Dict[str, Any]:
        doc = self.to_dict()
        # normalize to DB snake_case
        db = {
            '_id': doc.get('_id'),
            'species_code': doc.get('species_code'),
            'common_name': doc.get('common_name'),
            'scientific_name': doc.get('scientific_name'),
            'created_at': doc.get('created_at'),
            'metadata': doc.get('metadata')
        }
        for k, v in (self.extra or {}).items():
            if k not in db:
                db[k] = v
        return db

    def save(self, collection=None, repo=None, collection_name: Optional[str] = 'fish', upsert: bool = True):
        doc = self.to_db_doc()
        from fin_server.utils.time_utils import get_time_date_dt
        if 'created_at' not in doc or not doc['created_at']:
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
        # fallback
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        if upsert and doc.get('_id'):
            return coll.replace_one({'_id': doc['_id']}, doc, upsert=True)
        return coll.insert_one(doc)

    def update(self, filter_query: Dict[str, Any], update_fields: Dict[str, Any], collection=None, repo=None, collection_name: Optional[str] = 'fish'):
        if repo is not None and hasattr(repo, 'update'):
            return repo.update(filter_query, update_fields)
        if collection is None and repo is not None and hasattr(repo, 'get_collection'):
            collection = repo.get_collection(collection_name)
        if collection is not None:
            return collection.update_one(filter_query, {'$set': update_fields})
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        return coll.update_one(filter_query, {'$set': update_fields})
