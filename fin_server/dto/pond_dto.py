from typing import Optional, List, Dict, Any
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc


class StockRecordDTO:
    def __init__(self, id: Optional[str], pondId: str, species: str, quantity: float,
                 averageWeight: Optional[float], stockingDate: Optional[str], source: Optional[str],
                 batchId: Optional[str], expectedHarvestDate: Optional[str], extra: Dict[str, Any] = None):
        self.id = id
        self.pondId = pondId
        self.species = species
        self.quantity = float(quantity) if quantity is not None else 0.0
        self.averageWeight = float(averageWeight) if averageWeight is not None else None
        self.stockingDate = _to_iso_if_epoch(stockingDate) if stockingDate is not None else None
        self.source = source
        self.batchId = batchId
        self.expectedHarvestDate = _to_iso_if_epoch(expectedHarvestDate) if expectedHarvestDate is not None else None
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        doc = normalize_doc(doc)
        return cls(
            id=str(doc.get('_id')) if doc.get('_id') else doc.get('id'),
            pondId=doc.get('pond_id') or doc.get('pondId') or doc.get('pond'),
            species=doc.get('species') or doc.get('species_code'),
            quantity=doc.get('quantity') or doc.get('qty') or 0,
            averageWeight=doc.get('average_weight') or doc.get('averageWeight'),
            stockingDate=doc.get('stocking_date') or doc.get('stockingDate'),
            source=doc.get('source'),
            batchId=doc.get('batch_id') or doc.get('batchId'),
            expectedHarvestDate=doc.get('expected_harvest_date') or doc.get('expectedHarvestDate'),
            extra={k: v for k, v in doc.items() if k not in {'_id', 'pond_id', 'pondId', 'pond', 'species', 'species_code', 'quantity', 'qty', 'average_weight', 'averageWeight', 'stocking_date', 'stockingDate', 'source', 'batch_id', 'batchId', 'expected_harvest_date', 'expectedHarvestDate'}}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id'),
            pondId=payload.get('pondId') or payload.get('pond_id') or payload.get('pond'),
            species=payload.get('species') or payload.get('species_code'),
            quantity=payload.get('quantity') or payload.get('qty') or 0,
            averageWeight=payload.get('averageWeight') or payload.get('average_weight'),
            stockingDate=payload.get('stockingDate') or payload.get('stocking_date'),
            source=payload.get('source'),
            batchId=payload.get('batchId') or payload.get('batch_id'),
            expectedHarvestDate=payload.get('expectedHarvestDate') or payload.get('expected_harvest_date'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'pondId': self.pondId,
            'species': self.species,
            'quantity': self.quantity,
            'averageWeight': self.averageWeight,
            'stockingDate': self.stockingDate,
            'source': self.source,
            'batchId': self.batchId,
            'expectedHarvestDate': self.expectedHarvestDate,
            **self.extra
        }


class PondDTO:
    def __init__(self, id: Optional[str], name: str, dimensions: Optional[Dict[str, float]] = None,
                 volume: Optional[float] = None, type: Optional[str] = None, location: Optional[Dict[str, float]] = None,
                 currentStock: Optional[List[StockRecordDTO]] = None, waterQuality: Optional[List[Dict]] = None,
                 photos: Optional[List[str]] = None, createdAt: Optional[str] = None,
                 lastMaintenance: Optional[str] = None, status: Optional[str] = None, extra: Dict[str, Any] = None):
        self.id = id
        self.name = name
        self.dimensions = dimensions or {}
        self.volume = float(volume) if volume is not None else None
        self.type = type
        self.location = location or {}
        self.currentStock = currentStock or []
        self.waterQuality = waterQuality or []
        self.photos = photos or []
        self.createdAt = _to_iso_if_epoch(createdAt) if createdAt is not None else None
        self.lastMaintenance = _to_iso_if_epoch(lastMaintenance) if lastMaintenance is not None else None
        self.status = status
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        # gather stock records if present
        stocks = []
        for s in d.get('current_stock') or d.get('currentStock') or d.get('stocks') or []:
            try:
                stocks.append(StockRecordDTO.from_doc(s))
            except Exception:
                pass
        loc = d.get('location') or {}
        if isinstance(loc, str):
            loc = {}
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            name=d.get('pond_name') or d.get('pondName') or d.get('name'),
            dimensions=d.get('dimensions'),
            volume=d.get('volume') or d.get('capacity'),
            type=d.get('type') or d.get('water_type') or d.get('waterType'),
            location=loc,
            currentStock=stocks,
            waterQuality=d.get('water_quality') or d.get('waterQuality') or [],
            photos=d.get('photos') or [],
            createdAt=d.get('created_at') or d.get('createdAt'),
            lastMaintenance=d.get('last_maintenance') or d.get('lastMaintenance'),
            status=d.get('status'),
            extra={k: v for k, v in d.items() if k not in {'_id', 'pond_name', 'pondName', 'name', 'dimensions', 'volume', 'capacity', 'type', 'water_type', 'waterType', 'location', 'current_stock', 'currentStock', 'stocks', 'water_quality', 'waterQuality', 'photos', 'created_at', 'createdAt', 'last_maintenance', 'lastMaintenance', 'status'}}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        stocks = []
        for s in payload.get('currentStock', []) or payload.get('current_stock', []) or []:
            stocks.append(StockRecordDTO.from_request(s))
        return cls(
            id=payload.get('id') or payload.get('_id'),
            name=payload.get('name') or payload.get('pondName') or payload.get('pond_name'),
            dimensions=payload.get('dimensions'),
            volume=payload.get('volume'),
            type=payload.get('type') or payload.get('waterType'),
            location=payload.get('location'),
            currentStock=stocks,
            waterQuality=payload.get('waterQuality') or payload.get('water_quality'),
            photos=payload.get('photos'),
            createdAt=payload.get('createdAt') or payload.get('created_at'),
            lastMaintenance=payload.get('lastMaintenance') or payload.get('last_maintenance'),
            status=payload.get('status'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'dimensions': self.dimensions,
            'volume': self.volume,
            'type': self.type,
            'location': self.location,
            'currentStock': [s.to_dict() for s in self.currentStock],
            'waterQuality': self.waterQuality,
            'photos': self.photos,
            'createdAt': self.createdAt,
            'lastMaintenance': self.lastMaintenance,
            'status': self.status,
            **self.extra
        }

    def to_db_doc(self) -> Dict[str, Any]:
        doc = {
            'pond_id': self.id,
            'name': self.name,
            'dimensions': self.dimensions,
            'volume': self.volume,
            'type': self.type,
            'location': self.location,
            'current_stock': [s.to_db_doc() for s in self.currentStock],
            'water_quality': self.waterQuality,
            'photos': self.photos,
            'created_at': self.createdAt,
            'last_maintenance': self.lastMaintenance,
            'status': self.status
        }
        for k, v in (self.extra or {}).items():
            if k not in doc:
                doc[k] = v
        return doc

    def save(self, collection=None, repo=None, collection_name: Optional[str] = 'ponds', upsert: bool = True):
        doc = self.to_db_doc()
        from datetime import datetime, timezone
        if 'created_at' not in doc or not doc.get('created_at'):
            doc['created_at'] = datetime.now(timezone.utc)
        if repo is not None:
            try:
                if hasattr(repo, 'create'):
                    return repo.create(doc)
            except Exception:
                pass
            try:
                coll = repo.get_collection(collection_name)
                if coll:
                    if upsert and doc.get('pond_id'):
                        return coll.replace_one({'pond_id': doc['pond_id']}, doc, upsert=True)
                    return coll.insert_one(doc)
            except Exception:
                pass
        if collection is not None:
            if upsert and doc.get('pond_id'):
                return collection.replace_one({'pond_id': doc['pond_id']}, doc, upsert=True)
            return collection.insert_one(doc)
        from fin_server.repository.mongo_helper import MongoRepositorySingleton
        coll = MongoRepositorySingleton.get_instance().get_collection(collection_name)
        if upsert and doc.get('pond_id'):
            return coll.replace_one({'pond_id': doc['pond_id']}, doc, upsert=True)
        return coll.insert_one(doc)

    def update(self, filter_query: Dict[str, Any], update_fields: Dict[str, Any], collection=None, repo=None, collection_name: Optional[str] = 'ponds'):
        if repo is not None and hasattr(repo, 'update'):
            return repo.update(filter_query, update_fields)
        if collection is None and repo is not None and hasattr(repo, 'get_collection'):
            collection = repo.get_collection(collection_name)
        if collection is not None:
            return collection.update_one(filter_query, {'$set': update_fields})
        from fin_server.repository.mongo_helper import MongoRepositorySingleton
        coll = MongoRepositorySingleton.get_instance().get_collection(collection_name)
        return coll.update_one(filter_query, {'$set': update_fields})
