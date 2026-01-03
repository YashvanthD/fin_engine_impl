from typing import Optional, Dict, Any
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc
from fin_server.utils.normalizers import first_present


class GrowthRecordDTO:
    def __init__(self, id: Optional[str], pondId: str, species: str, samplingDate: str, sampleSize: int,
                 averageWeight: float, averageLength: float, survivalRate: float, feedConversionRatio: float,
                 cost: float, recordedBy: Optional[str], notes: Optional[str], extra: Dict[str, Any] = None):
        self.id = id
        self.pondId = pondId
        self.species = species
        self.samplingDate = _to_iso_if_epoch(samplingDate) if samplingDate is not None else None
        self.sampleSize = int(sampleSize) if sampleSize is not None else None
        self.averageWeight = float(averageWeight) if averageWeight is not None else None
        self.averageLength = float(averageLength) if averageLength is not None else None
        self.survivalRate = float(survivalRate) if survivalRate is not None else None
        self.feedConversionRatio = float(feedConversionRatio) if feedConversionRatio is not None else None
        self.cost = float(cost) if cost is not None else None
        self.recordedBy = recordedBy
        self.notes = notes
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            pondId=first_present(d, ['pondId', 'pond_id', 'pond']),
            species=first_present(d, ['species', 'species_code']),
            samplingDate=first_present(d, ['sampling_date', 'samplingDate']),
            sampleSize=first_present(d, ['sample_size', 'sampleSize']),
            averageWeight=first_present(d, ['average_weight', 'averageWeight']),
            averageLength=first_present(d, ['average_length', 'averageLength']),
            survivalRate=first_present(d, ['survival_rate', 'survivalRate']),
            feedConversionRatio=first_present(d, ['feed_conversion_ratio', 'feedConversionRatio']),
            cost=first_present(d, ['cost', 'cost_amount', 'total_cost']),
            recordedBy=first_present(d, ['recordedBy', 'recorded_by']),
            notes=d.get('notes'),
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id') or payload.get('_id'),
            pondId=first_present(payload, ['pondId', 'pond_id', 'pond']),
            species=first_present(payload, ['species', 'species_code']),
            samplingDate=first_present(payload, ['samplingDate', 'sampling_date']),
            sampleSize=first_present(payload, ['sampleSize', 'sample_size']),
            averageWeight=first_present(payload, ['averageWeight', 'average_weight']),
            averageLength=first_present(payload, ['averageLength', 'average_length']),
            survivalRate=first_present(payload, ['survivalRate', 'survival_rate']),
            feedConversionRatio=first_present(payload, ['feedConversionRatio', 'feed_conversion_ratio']),
            cost=first_present(payload, ['cost', 'cost_amount', 'total_cost']),
            recordedBy=first_present(payload, ['recordedBy', 'recorded_by']),
            notes=payload.get('notes'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        # Canonical API representation uses camelCase keys
        out: Dict[str, Any] = {
            'id': self.id,
            'pondId': self.pondId,
            'species': self.species,
            'samplingDate': self.samplingDate,
            'sampleSize': self.sampleSize,
            'averageWeight': self.averageWeight,
            'averageLength': self.averageLength,
            'survivalRate': self.survivalRate,
            'feedConversionRatio': self.feedConversionRatio,
            'cost': self.cost,
            'recordedBy': self.recordedBy,
            'notes': self.notes,
        }

        # Promote some canonical snake_case extras (if present) into camelCase response fields
        # so clients always see a single representation for totals/units
        if isinstance(self.extra, dict):
            # mapping of canonical snake_case -> desired camelCase in response
            promote_map = {
                'total_cost': 'totalAmount',
                'cost_unit': 'costUnit',
                'total_count': 'totalCount'
            }
            for snake_key, camel_key in promote_map.items():
                if snake_key in self.extra and self.extra.get(snake_key) is not None and out.get(camel_key) is None:
                    out[camel_key] = self.extra.get(snake_key)

            # When merging extra, skip keys that are aliases of core fields to avoid duplicates
            alias_keys = {
                'pondId', 'pond_id', 'pond',
                'samplingDate', 'sampling_date',
                'sampleSize', 'sample_size',
                'averageWeight', 'average_weight',
                'averageLength', 'average_length',
                'survivalRate', 'survival_rate',
                'feedConversionRatio', 'feed_conversion_ratio',
                'cost', 'cost_amount', 'total_cost', 'totalAmount', 'total_amount',
                'recordedBy', 'recorded_by',
                'notes',
                'costUnit', 'cost_unit',
                'type'
            }

            for k, v in self.extra.items():
                if k in alias_keys:
                    # skip alias keys or core fields
                    continue
                # skip null values from extra
                if v is None:
                    continue
                if k not in out:
                    out[k] = v
        # Remove any keys with None values so API doesn't send nulls (but keep falsy numeric/empty-collection values)
        return {k: v for k, v in out.items() if v is not None}

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
            'cost': self.cost,
            'recorded_by': self.recordedBy,
            'notes': self.notes
        }
        # Persist sampling-specific metadata if present in extra
        # - type -> type
        # - totalAmount -> total_cost (so older code that checks total_cost/cost_amount works)
        # - costUnit / cost_unit -> cost_unit
        if isinstance(self.extra, dict):
            ta = None
            # accept camelCase or snake_case keys
            if 'totalAmount' in self.extra and self.extra.get('totalAmount') not in (None, ''):
                ta = self.extra.get('totalAmount')
            elif 'total_amount' in self.extra and self.extra.get('total_amount') not in (None, ''):
                ta = self.extra.get('total_amount')
            if ta is not None and 'total_cost' not in doc and 'cost_amount' not in doc:
                try:
                    doc['total_cost'] = float(ta)
                except Exception:
                    doc['total_cost'] = ta

            # cost unit
            cu = None
            if 'costUnit' in self.extra and self.extra.get('costUnit') not in (None, ''):
                cu = self.extra.get('costUnit')
            elif 'cost_unit' in self.extra and self.extra.get('cost_unit') not in (None, ''):
                cu = self.extra.get('cost_unit')
            if cu is not None and 'cost_unit' not in doc:
                doc['cost_unit'] = cu

            # total count
            tc = None
            if 'totalCount' in self.extra and self.extra.get('totalCount') not in (None, ''):
                tc = self.extra.get('totalCount')
            elif 'total_count' in self.extra and self.extra.get('total_count') not in (None, ''):
                tc = self.extra.get('total_count')
            if tc is not None and 'total_count' not in doc:
                try:
                    doc['total_count'] = int(float(tc))
                except Exception:
                    doc['total_count'] = tc

            # type
            t = None
            if 'type' in self.extra and self.extra.get('type') not in (None, ''):
                t = self.extra.get('type')
            if t is not None and 'type' not in doc:
                doc['type'] = t

        # Avoid inserting duplicate alias keys present in extra (camelCase) that map to canonical fields
        alias_keys = {
            'pondId', 'pond_id', 'pond',
            'samplingDate', 'sampling_date',
            'sampleSize', 'sample_size',
            'averageWeight', 'average_weight',
            'averageLength', 'average_length',
            'survivalRate', 'survival_rate',
            'feedConversionRatio', 'feed_conversion_ratio',
            'cost', 'cost_amount', 'total_cost', 'totalAmount', 'total_amount',
            'recordedBy', 'recorded_by',
            'notes',
            'costUnit', 'cost_unit',
            'type', 'totalCount', 'total_count'
        }

        for k, v in (self.extra or {}).items():
            if k in alias_keys:
                # skip aliases; core fields already in doc or handled above
                continue
            if k not in doc:
                doc[k] = v
        # Remove keys with None values so we don't store nulls in DB
        return {k: v for k, v in doc.items() if v is not None}

    def save(self, collection=None, repo=None, collection_name: Optional[str] = 'sampling', upsert: bool = False):
        doc = self.to_db_doc()
        from fin_server.utils.time_utils import get_time_date_dt
        if 'created_at' not in doc:
            doc['created_at'] = get_time_date_dt(include_time=True)
        if repo is not None:
            if hasattr(repo, 'create'):
                return repo.create(doc)
            # If repo exposes insert_one directly (collection adapter), use it
            if hasattr(repo, 'insert_one'):
                return repo.insert_one(doc)
            # Otherwise attempt to get a collection from repo
            if hasattr(repo, 'get_collection'):
                coll = repo.get_collection(collection_name)
                return coll.insert_one(doc)
        if collection is not None:
            return collection.insert_one(doc)
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        return coll.insert_one(doc)

    def update(self, filter_query: Dict[str, Any], update_fields: Dict[str, Any], collection=None, repo=None, collection_name: Optional[str] = 'sampling'):
        if repo is not None and hasattr(repo, 'update'):
            return repo.update(filter_query, update_fields)
        if repo is not None and hasattr(repo, 'update_one'):
            return repo.update_one(filter_query, {'$set': update_fields})
        if collection is not None:
            return collection.update_one(filter_query, {'$set': update_fields})
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        return coll.update_one(filter_query, {'$set': update_fields})
