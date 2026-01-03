from typing import Optional, List, Dict, Any
from fin_server.repository.mongo_helper import get_collection
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
        try:
            self.stock_coll = get_collection('ponds')
        except Exception:
            self.stock_coll = None

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
        out = {
            'id': self.id,
            'pondId': self.pondId,
            'species': self.species,
            'quantity': self.quantity,
            'averageWeight': self.averageWeight,
            'stockingDate': self.stockingDate,
            'source': self.source,
            'batchId': self.batchId,
            'expectedHarvestDate': self.expectedHarvestDate,
        }
        # include non-null extra fields
        if isinstance(self.extra, dict):
            for k, v in self.extra.items():
                if v is None:
                    continue
                if k not in out:
                    out[k] = v
        # remove None values
        return {k: v for k, v in out.items() if v is not None}
