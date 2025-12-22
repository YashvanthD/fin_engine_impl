from typing import Optional, Dict, Any
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc


class AlertDTO:
    def __init__(self, id: Optional[str], type: str, severity: str, title: str, message: str,
                 pondId: Optional[str], timestamp: str, acknowledged: bool, acknowledgedBy: Optional[str],
                 acknowledgedAt: Optional[str], extra: Dict[str, Any] = None):
        self.id = id
        self.type = type
        self.severity = severity
        self.title = title
        self.message = message
        self.pondId = pondId
        self.timestamp = _to_iso_if_epoch(timestamp) if timestamp is not None else None
        self.acknowledged = bool(acknowledged)
        self.acknowledgedBy = acknowledgedBy
        self.acknowledgedAt = _to_iso_if_epoch(acknowledgedAt) if acknowledgedAt is not None else None
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id'),
            type=d.get('type'),
            severity=d.get('severity'),
            title=d.get('title'),
            message=d.get('message'),
            pondId=d.get('pondId') or d.get('pond_id'),
            timestamp=d.get('timestamp') or d.get('created_at'),
            acknowledged=d.get('acknowledged') or False,
            acknowledgedBy=d.get('acknowledgedBy') or d.get('acknowledged_by'),
            acknowledgedAt=d.get('acknowledgedAt') or d.get('acknowledged_at'),
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id') or payload.get('_id'),
            type=payload.get('type'),
            severity=payload.get('severity'),
            title=payload.get('title'),
            message=payload.get('message'),
            pondId=payload.get('pondId') or payload.get('pond_id'),
            timestamp=payload.get('timestamp') or payload.get('created_at'),
            acknowledged=payload.get('acknowledged') or False,
            acknowledgedBy=payload.get('acknowledgedBy') or payload.get('acknowledged_by'),
            acknowledgedAt=payload.get('acknowledgedAt') or payload.get('acknowledged_at'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'pondId': self.pondId,
            'timestamp': self.timestamp,
            'acknowledged': self.acknowledged,
            'acknowledgedBy': self.acknowledgedBy,
            'acknowledgedAt': self.acknowledgedAt,
            **self.extra
        }

