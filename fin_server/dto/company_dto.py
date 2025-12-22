from typing import Optional, Dict, Any
from fin_server.utils.helpers import normalize_doc, _to_iso_if_epoch


class CompanyDTO:
    def __init__(self, account_key: str, company_name: str, created_date: Optional[str] = None, description: Optional[str] = None, pincode: Optional[str] = None, employee_count: Optional[int] = None, admin_user_key: Optional[str] = None, users: Optional[list] = None, extra: Dict[str, Any] = None):
        self.account_key = account_key
        self.company_name = company_name
        self.created_date = _to_iso_if_epoch(created_date) if created_date is not None else None
        self.description = description
        self.pincode = pincode
        self.employee_count = employee_count
        self.admin_user_key = admin_user_key
        self.users = users or []
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]):
        d = normalize_doc(doc)
        return cls(
            account_key=d.get('account_key'),
            company_name=d.get('company_name'),
            created_date=d.get('created_date') or d.get('createdDate'),
            description=d.get('description'),
            pincode=d.get('pincode'),
            employee_count=d.get('employee_count') or d.get('employeeCount'),
            admin_user_key=d.get('admin_user_key'),
            users=d.get('users') or [],
            extra={k: v for k, v in d.items()}
        )

    def to_dict(self) -> Dict[str, Any]:
        out = {
            'account_key': self.account_key,
            'company_name': self.company_name,
            'created_date': self.created_date,
            'description': self.description,
            'pincode': self.pincode,
            'employee_count': self.employee_count,
            'admin_user_key': self.admin_user_key,
            'users': self.users,
        }
        out.update(self.extra or {})
        return out

