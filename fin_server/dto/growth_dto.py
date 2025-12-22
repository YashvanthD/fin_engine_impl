from typing import Optional, Dict, Any
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc


class GrowthRecordDTO:
    def __init__(self, id: Optional[str], pondId: str, species: str, samplingDate: str, sampleSize: int,
                 averageWeight: float, averageLength: float, survivalRate: float, feedConversionRatio: float,
                 recordedBy: Optional[str], notes: Optional[str], extra: Dict[str, Any] = None):
        self.id = id
        self.pondId = pondId
        self.species = species
        self.samplingDate = _to_iso_if_epoch(samplingDate) if samplingDate is not None else None
        self.sampleSize = int(sampleSize) if sampleSize is not None else None
        self.averageWeight = float(averageWeight) if averageWeight is not None else None
        self.averageLength = float(averageLength) if averageLength is not None else None
        self.survivalRate = float(survivalRate) if survivalRate is not None else None
        self.feedConversionRatio = float(feedConversionRatio) if feedConversionRatio is not None else None
        self.recordedBy = recordedBy
        self.notes = notes
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            pondId=d.get('pondId') or d.get('pond_id') or d.get('pond'),
            species=d.get('species') or d.get('species_code'),
            samplingDate=d.get('sampling_date') or d.get('samplingDate'),
            sampleSize=d.get('sample_size') or d.get('sampleSize'),
            averageWeight=d.get('average_weight') or d.get('averageWeight'),
            averageLength=d.get('average_length') or d.get('averageLength'),
            survivalRate=d.get('survival_rate') or d.get('survivalRate'),
            feedConversionRatio=d.get('feed_conversion_ratio') or d.get('feedConversionRatio'),
            recordedBy=d.get('recordedBy') or d.get('recorded_by'),
            notes=d.get('notes'),
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id') or payload.get('_id'),
            pondId=payload.get('pondId') or payload.get('pond_id') or payload.get('pond'),
            species=payload.get('species') or payload.get('species_code'),
            samplingDate=payload.get('samplingDate') or payload.get('sampling_date'),
            sampleSize=payload.get('sampleSize') or payload.get('sample_size'),
            averageWeight=payload.get('averageWeight') or payload.get('average_weight'),
            averageLength=payload.get('averageLength') or payload.get('average_length'),
            survivalRate=payload.get('survivalRate') or payload.get('survival_rate'),
            feedConversionRatio=payload.get('feedConversionRatio') or payload.get('feed_conversion_ratio'),
            recordedBy=payload.get('recordedBy') or payload.get('recorded_by'),
            notes=payload.get('notes'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'pondId': self.pondId,
            'species': self.species,
            'samplingDate': self.samplingDate,
            'sampleSize': self.sampleSize,
            'averageWeight': self.averageWeight,
            'averageLength': self.averageLength,
            'survivalRate': self.survivalRate,
            'feedConversionRatio': self.feedConversionRatio,
            'recordedBy': self.recordedBy,
            'notes': self.notes,
            **self.extra
        }

    def to_db_doc(self) -> Dict[str, Any]:
        doc = {
            'pond_id': self.pondId,
            'species': self.species,
            'sampling_date': self.samplingDate,
            'sample_size': self.sampleSize,
            'average_weight': self.averageWeight,
            'average_length': self.averageLength,
            'survival_rate': self.survivalRate,
            'feed_conversion_ratio': self.feedConversionRatio,
            'recorded_by': self.recordedBy,
            'notes': self.notes
        }
        for k, v in (self.extra or {}).items():
            if k not in doc:
                doc[k] = v
        return doc

    def save(self, collection=None, repo=None, collection_name: Optional[str] = 'sampling', upsert: bool = False):
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
        from fin_server.repository.mongo_helper import MongoRepositorySingleton
        coll = MongoRepositorySingleton.get_instance().get_collection(collection_name)
        if upsert and doc.get('_id'):
            return coll.replace_one({'_id': doc['_id']}, doc, upsert=True)
        return coll.insert_one(doc)

    def update(self, filter_query: Dict[str, Any], update_fields: Dict[str, Any], collection=None, repo=None, collection_name: Optional[str] = 'sampling'):
        if repo is not None and hasattr(repo, 'update'):
            return repo.update(filter_query, update_fields)
        if collection is None and repo is not None and hasattr(repo, 'get_collection'):
            collection = repo.get_collection(collection_name)
        if collection is not None:
            return collection.update_one(filter_query, {'$set': update_fields})
        from fin_server.repository.mongo_helper import MongoRepositorySingleton
        coll = MongoRepositorySingleton.get_instance().get_collection(collection_name)
        return coll.update_one(filter_query, {'$set': update_fields})
