from typing import Dict, Any, Optional
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.time_utils import get_time_date_dt
from fin_server.utils.generator import generate_account_number


def create_bank_account_for_user(user_doc: Dict[str, Any], account_type: str = 'current') -> Any:
    """Create a bank account record mapped to a user.

    The bank account will be stored in the `bank_accounts` collection and will contain:
      - account_number
      - user_key
      - account_key (organization)
      - balance (default 0)
      - type / account_type
      - createdAt

    Returns the inserted_id.
    """
    bank_accounts = get_collection('bank_accounts')
    # If a bank account for this user already exists, raise an error (do not create duplicate)
    user_key = user_doc.get('user_key')
    try:
        existing = bank_accounts.find_one({'user_key': user_key})
    except Exception:
        coll = getattr(bank_accounts, 'collection', bank_accounts)
        existing = coll.find_one({'user_key': user_key})
    if existing:
        raise ValueError(f"Bank account already exists for user {user_key}")
    # Build record
    rec = {
        'account_number': generate_account_number(),
        'user_key': user_doc.get('user_key'),
        'account_key': user_doc.get('account_key'),
        'balance': float(user_doc.get('initial_balance', 0) or 0),
        'type': 'user',
        'account_type': account_type,
        'created_at': get_time_date_dt(include_time=True)
    }
    # Use repository API if available
    if hasattr(bank_accounts, 'create'):
        r = bank_accounts.create(rec)
        return getattr(r, 'inserted_id', None)
    if hasattr(bank_accounts, 'insert_one'):
        r = bank_accounts.insert_one(rec)
        return getattr(r, 'inserted_id', None)
    # fallback
    return None


def ensure_organization_account(account_key: str, account_name: Optional[str] = None) -> Any:
    """Ensure there is a bank account record for the organization (account_key).

    Returns the bank account doc or inserted_id.
    """
    bank_accounts = get_collection('bank_accounts')
    # try find
    try:
        existing = bank_accounts.find_one({'account_key': account_key, 'type': 'organization'})
    except Exception:
        # repository may expose .collection
        coll = getattr(bank_accounts, 'collection', bank_accounts)
        existing = coll.find_one({'account_key': account_key, 'type': 'organization'})
    if existing:
        # Organization account already exists; raise rather than silently returning
        raise ValueError(f"Organization bank account already exists for account_key {account_key}")
    rec = {
        'account_number': generate_account_number(),
        'account_key': account_key,
        'name': account_name or account_key,
        'balance': 0.0,
        'type': 'organization',
        'account_type': 'current',
        'created_at': get_time_date_dt(include_time=True)
    }
    if hasattr(bank_accounts, 'create'):
        r = bank_accounts.create(rec)
        return getattr(r, 'inserted_id', None)
    coll = getattr(bank_accounts, 'collection', bank_accounts)
    r = coll.insert_one(rec)
    return getattr(r, 'inserted_id', None)


def create_user_and_accounts(user_repo, user_doc: Dict[str, Any], create_user_bank: bool = True, ensure_org_account: bool = True) -> Dict[str, Any]:
    """Create user via provided user_repo and create bank accounts as needed.

    Returns a dict with keys: user_id, user_bank_account_id, org_account_id
    """
    res = {'user_id': None, 'user_bank_account_id': None, 'org_account_id': None}
    # create user using repository interface
    if hasattr(user_repo, 'create'):
        user_id = user_repo.create(user_doc)
    else:
        # fallback: insert_one
        coll = getattr(user_repo, 'collection', user_repo)
        r = coll.insert_one(user_doc)
        user_id = getattr(r, 'inserted_id', None)
    res['user_id'] = user_id

    # create user bank account (if requested) -- let errors propagate if account exists
    if create_user_bank:
        uba = create_bank_account_for_user(user_doc)
        res['user_bank_account_id'] = uba

    # ensure org account exists
    if ensure_org_account:
        org = ensure_organization_account(user_doc.get('account_key'))
        res['org_account_id'] = org

    return res

