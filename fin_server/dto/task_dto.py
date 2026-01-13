from typing import Optional, Dict, Any, List
from fin_server.utils.helpers import _to_iso_if_epoch, normalize_doc


class TaskDTO:
    def __init__(self, id: Optional[str], title: str, description: Optional[str] = None,
                 type: Optional[str] = None, taskType: Optional[str] = None, pondId: Optional[str] = None,
                 assignedTo: Optional[str] = None, status: Optional[str] = 'pending', priority: Optional[Any] = 'pending',
                 scheduledDate: Optional[str] = None, startTime: Optional[str] = None, endTime: Optional[str] = None,
                 completedDate: Optional[str] = None, estimatedDuration: Optional[float] = None, photos: Optional[List[str]] = None,
                 notes: Optional[str] = None, recurring: Optional[dict] = None, extra: Dict[str, Any] = None):
        self.id = id
        self.title = title
        self.description = description
        self.type = type
        self.taskType = taskType
        self.pondId = pondId
        self.assignedTo = assignedTo
        self.status = status
        self.priority = priority
        self.scheduledDate = _to_iso_if_epoch(scheduledDate) if scheduledDate else None
        self.startTime = _to_iso_if_epoch(startTime) if startTime else None
        self.endTime = _to_iso_if_epoch(endTime) if endTime else None
        self.completedDate = _to_iso_if_epoch(completedDate) if completedDate else None
        self.estimatedDuration = float(estimatedDuration) if estimatedDuration is not None else None
        self.photos = photos or []
        self.notes = notes
        self.recurring = recurring or {}
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        return cls(
            id=str(d.get('_id')) if d.get('_id') else d.get('id') or d.get('task_id'),
            title=d.get('title'),
            description=d.get('description'),
            type=d.get('type'),
            taskType=d.get('taskType') or d.get('task_type'),
            pondId=d.get('pondId') or d.get('pond_id'),
            assignedTo=d.get('assignee') or d.get('assignedTo'),
            status=d.get('status'),
            priority=d.get('priority'),
            scheduledDate=d.get('scheduledDate') or d.get('task_date') or d.get('taskDate'),
            startTime=d.get('startTime') or d.get('start_time'),
            endTime=d.get('endTime') or d.get('end_date') or d.get('endDate'),
            completedDate=d.get('completedDate') or d.get('completed_date'),
            estimatedDuration=d.get('estimatedDuration') or d.get('estimated_duration'),
            photos=d.get('photos'),
            notes=d.get('notes'),
            recurring=d.get('recurring'),
            extra={k: v for k, v in d.items()}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            id=payload.get('id') or payload.get('_id') or payload.get('task_id'),
            title=payload.get('title'),
            description=payload.get('description'),
            type=payload.get('type'),
            taskType=payload.get('taskType') or payload.get('task_type'),
            pondId=payload.get('pondId') or payload.get('pond_id'),
            assignedTo=payload.get('assignee') or payload.get('assignedTo'),
            status=payload.get('status'),
            priority=payload.get('priority'),
            scheduledDate=payload.get('scheduledDate') or payload.get('task_date') or payload.get('taskDate'),
            startTime=payload.get('startTime') or payload.get('start_time'),
            endTime=payload.get('endTime') or payload.get('end_date'),
            completedDate=payload.get('completedDate') or payload.get('completed_date'),
            estimatedDuration=payload.get('estimatedDuration') or payload.get('estimated_duration'),
            photos=payload.get('photos'),
            notes=payload.get('notes'),
            recurring=payload.get('recurring'),
            extra={k: v for k, v in payload.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        out = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'type': self.type,
            'taskType': self.taskType,
            'pondId': self.pondId,
            'assignedTo': self.assignedTo,
            'status': self.status,
            'priority': self.priority,
            'scheduledDate': self.scheduledDate,
            'startTime': self.startTime,
            'endTime': self.endTime,
            'completedDate': self.completedDate,
            'estimatedDuration': self.estimatedDuration,
            'photos': self.photos,
            'notes': self.notes,
            'recurring': self.recurring,
        }
        # merge extras
        out.update(self.extra or {})
        return out

    def to_db_doc(self) -> Dict[str, Any]:
        doc = self.to_dict()
        db = {
            'task_id': doc.get('id'),
            'title': doc.get('title'),
            'description': doc.get('description'),
            'type': doc.get('type'),
            'task_type': doc.get('taskType') or doc.get('task_type'),
            'pond_id': doc.get('pondId'),
            'assignee': doc.get('assignedTo'),
            'status': doc.get('status'),
            'priority': doc.get('priority'),
            'task_date': doc.get('scheduledDate'),
            'start_time': doc.get('startTime'),
            'end_date': doc.get('endTime'),
            'completed_date': doc.get('completedDate'),
            'estimated_duration': doc.get('estimatedDuration'),
            'photos': doc.get('photos'),
            'notes': doc.get('notes'),
            'recurring': doc.get('recurring')
        }
        for k, v in (self.extra or {}).items():
            if k not in db:
                db[k] = v
        return db

    def save(self, collection=None, repo=None, collection_name: Optional[str] = 'tasks', upsert: bool = True):
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
                    if upsert and doc.get('task_id'):
                        return coll.replace_one({'task_id': doc['task_id']}, doc, upsert=True)
                    return coll.insert_one(doc)
            except Exception:
                pass
        if collection is not None:
            if upsert and doc.get('task_id'):
                return collection.replace_one({'task_id': doc['task_id']}, doc, upsert=True)
            return collection.insert_one(doc)
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        if upsert and doc.get('task_id'):
            return coll.replace_one({'task_id': doc['task_id']}, doc, upsert=True)
        return coll.insert_one(doc)

    def update(self, filter_query: Dict[str, Any], update_fields: Dict[str, Any], collection=None, repo=None, collection_name: Optional[str] = 'tasks'):
        if repo is not None and hasattr(repo, 'update'):
            return repo.update(filter_query, update_fields)
        if collection is None and repo is not None and hasattr(repo, 'get_collection'):
            collection = repo.get_collection(collection_name)
        if collection is not None:
            return collection.update_one(filter_query, {'$set': update_fields})
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        return coll.update_one(filter_query, {'$set': update_fields})
