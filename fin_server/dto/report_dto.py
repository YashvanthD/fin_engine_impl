from typing import Optional, Dict, Any, List
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc


class ReportDTO:
    def __init__(self, id: Optional[str], title: str, type: str, dateRange: Dict[str, str], ponds: List[str],
                 generatedBy: str, generatedAt: str, data: Any, extra: Dict[str, Any] = None):
        self.id = id
        self.title = title
        self.type = type
        self.dateRange = {'start': _to_iso_if_epoch(dateRange.get('start')) if dateRange and dateRange.get('start') else None,
                          'end': _to_iso_if_epoch(dateRange.get('end')) if dateRange and dateRange.get('end') else None}
        self.ponds = ponds or []
        self.generatedBy = generatedBy
        self.generatedAt = _to_iso_if_epoch(generatedAt) if generatedAt is not None else None
        self.data = data
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        dr = d.get('dateRange') or {'start': d.get('start_date') or d.get('from'), 'end': d.get('end_date') or d.get('to')}
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            title=d.get('title'),
            type=d.get('type'),
            dateRange=dr,
            ponds=d.get('ponds') or [],
            generatedBy=d.get('generatedBy') or d.get('generated_by'),
            generatedAt=d.get('generatedAt') or d.get('generated_at'),
            data=d.get('data'),
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        dr = payload.get('dateRange') or {'start': payload.get('start') or payload.get('from'), 'end': payload.get('end') or payload.get('to')}
        return cls(
            id=payload.get('id') or payload.get('_id'),
            title=payload.get('title'),
            type=payload.get('type'),
            dateRange=dr,
            ponds=payload.get('ponds') or [],
            generatedBy=payload.get('generatedBy') or payload.get('generated_by'),
            generatedAt=payload.get('generatedAt') or payload.get('generated_at'),
            data=payload.get('data'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'type': self.type,
            'dateRange': self.dateRange,
            'ponds': self.ponds,
            'generatedBy': self.generatedBy,
            'generatedAt': self.generatedAt,
            'data': self.data,
            **self.extra
        }

