import base64
import random
import re
import time

from fin_server.repository.mongo_helper import get_collection
from fin_server.requests.subscription import default_subscription
from fin_server.security.authentication import AuthSecurity
from fin_server.utils.time_utils import get_time_date_dt, get_time_date as _get_time_date

user_repo = get_collection('users')


def generate_key(
    length=6,
    include_alphabets=False,
    include_special=False,
    include_numbers=True,
    uppercase_only=False,
    lowercase_only=False
):
    """Generate a random key of the requested length.

    Args:
        length: Length of the generated key
        include_alphabets: Include letters (A-Z, a-z)
        include_special: Include special characters (!@#$%^&*()-_=+)
        include_numbers: Include digits (0-9)
        uppercase_only: Only uppercase letters (when include_alphabets=True)
        lowercase_only: Only lowercase letters (when include_alphabets=True)

    Returns:
        Random string of specified length

    Raises:
        ValueError: If no character set is selected
    """
    includes = ''

    if include_numbers:
        includes += '0123456789'

    if include_alphabets:
        if uppercase_only:
            includes += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        elif lowercase_only:
            includes += 'abcdefghijklmnopqrstuvwxyz'
        else:
            includes += 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

    if include_special:
        includes += '!@#$%^&*()-_=+'

    if not includes:
        raise ValueError("At least one character set must be selected")

    return ''.join(random.choice(includes) for _ in range(int(length)))


# ============================================================================
# CONSISTENT ID GENERATORS
# ============================================================================
# ID Format Standards:
#   - account_key:      6 numeric digits (e.g., "123456")
#   - user_key:         9 numeric digits (e.g., "123456789")
#   - message_id:       12 alphanumeric chars (e.g., "aB3dE5fG7hJ9")
#   - transaction_id:   12 alphanumeric chars (e.g., "TXN-aB3dE5fG7h")
#   - expense_id:       12 alphanumeric chars (e.g., "EXP-aB3dE5fG7h")
#   - pond_id:          account_key + 3 digits (e.g., "123456-001")
#   - pond_event_id:    12 alphanumeric chars (e.g., "EVT-aB3dE5fG7h")
#   - fish_event_id:    12 alphanumeric chars (e.g., "FEV-aB3dE5fG7h")
#   - batch_id:         12 alphanumeric chars (e.g., "BAT-aB3dE5fG7h")
#   - sampling_id:      12 alphanumeric chars (e.g., "SMP-aB3dE5fG7h")
#   - species_code:     5 chars from name + 5 numeric digits (e.g., "TILAP-00001")
#   - account_number:   12 numeric digits (e.g., "572137000001")
# ============================================================================


def generate_account_key() -> str:
    """Generate a 6-digit numeric account key.

    Format: 6 numeric digits (e.g., "123456")
    Used to identify an organization/company.
    """
    return generate_key(length=6, include_numbers=True, include_alphabets=False)


def generate_user_key() -> str:
    """Generate a 9-digit numeric user key.

    Format: 9 numeric digits (e.g., "123456789")
    Used to identify individual users within the system.
    """
    return generate_key(length=9, include_numbers=True, include_alphabets=False)


def generate_alphanumeric_id(length=12) -> str:
    """Generate an alphanumeric ID of specified length.

    Format: Alphanumeric characters (A-Z, a-z, 0-9)
    Base generator for various ID types.
    """
    return generate_key(length=length, include_numbers=True, include_alphabets=True)


def generate_message_id() -> str:
    """Generate a 12-character alphanumeric message ID.

    Format: MSG-<9 alphanumeric chars> (e.g., "MSG-aB3dE5fG7")
    Used for chat/messaging system.
    """
    return f"MSG-{generate_alphanumeric_id(9)}"


def generate_transaction_id() -> str:
    """Generate a 12-character alphanumeric transaction ID.

    Format: TXN-<9 alphanumeric chars> (e.g., "TXN-aB3dE5fG7")
    Used for financial transactions.
    """
    return f"TXN-{generate_alphanumeric_id(9)}"


def generate_expense_id() -> str:
    """Generate a 12-character alphanumeric expense ID.

    Format: EXP-<9 alphanumeric chars> (e.g., "EXP-aB3dE5fG7")
    Used for expense records.
    """
    return f"EXP-{generate_alphanumeric_id(9)}"


def generate_pond_id(account_key: str) -> str:
    """Generate a pond ID based on account_key.

    Format: <account_key>-<3 digits> (e.g., "123456-001")
    Sequential within the account.

    Args:
        account_key: The 6-digit account key

    Returns:
        Pond ID in format "XXXXXX-NNN"
    """
    try:
        ponds_coll = get_collection('ponds')
        coll = getattr(ponds_coll, 'collection', ponds_coll)
        # Find highest pond number for this account
        cursor = coll.find(
            {'account_key': account_key},
            {'pond_id': 1}
        ).sort('pond_id', -1).limit(1)

        max_num = 0
        for doc in cursor:
            pond_id = doc.get('pond_id', '')
            if '-' in pond_id:
                try:
                    num = int(pond_id.split('-')[-1])
                    if num > max_num:
                        max_num = num
                except (ValueError, IndexError):
                    pass

        next_num = max_num + 1
    except Exception:
        # Fallback to random if DB access fails
        next_num = random.randint(1, 999)

    return f"{account_key}-{next_num:03d}"


def generate_pond_event_id() -> str:
    """Generate a 12-character alphanumeric pond event ID.

    Format: PEV-<9 alphanumeric chars> (e.g., "PEV-aB3dE5fG7")
    Used for pond-related events (stocking, transfer, harvest, etc.)
    """
    return f"PEV-{generate_alphanumeric_id(9)}"


def generate_fish_event_id() -> str:
    """Generate a 12-character alphanumeric fish event ID.

    Format: FEV-<9 alphanumeric chars> (e.g., "FEV-aB3dE5fG7")
    Used for fish-related events (mortality, growth, feeding, etc.)
    """
    return f"FEV-{generate_alphanumeric_id(9)}"


def generate_batch_id() -> str:
    """Generate a 12-character alphanumeric batch ID.

    Format: BAT-<9 alphanumeric chars> (e.g., "BAT-aB3dE5fG7")
    Used for fish batch tracking.
    """
    return f"BAT-{generate_alphanumeric_id(9)}"


def generate_new_sampling_id() -> str:
    """Generate a 12-character alphanumeric sampling ID.

    Format: SMP-<9 alphanumeric chars> (e.g., "SMP-aB3dE5fG7")
    Used for sampling/growth records.
    """
    return f"SMP-{generate_alphanumeric_id(9)}"


def generate_species_code(name: str) -> str:
    """Generate a species code from scientific/common name.

    Format: <5 chars from name>-<5 numeric digits> (e.g., "TILAP-00001")

    Args:
        name: Scientific name, common name, or any available name

    Returns:
        Species code in format "XXXXX-NNNNN"
    """
    # Clean and extract first 5 meaningful characters
    clean_name = re.sub(r'[^a-zA-Z]', '', name).upper()
    prefix = clean_name[:5].ljust(5, 'X')  # Pad with X if less than 5 chars

    try:
        fish_coll = get_collection('fish')
        coll = getattr(fish_coll, 'collection', fish_coll)
        # Find highest number for this prefix
        cursor = coll.find(
            {'species_code': {'$regex': f'^{prefix}-'}},
            {'species_code': 1}
        ).sort('species_code', -1).limit(1)

        max_num = 0
        for doc in cursor:
            code = doc.get('species_code', '')
            if '-' in code:
                try:
                    num = int(code.split('-')[-1])
                    if num > max_num:
                        max_num = num
                except (ValueError, IndexError):
                    pass

        next_num = max_num + 1
    except Exception:
        # Fallback to random if DB access fails
        next_num = random.randint(1, 99999)

    return f"{prefix}-{next_num:05d}"


def generate_task_id() -> str:
    """Generate a 12-character alphanumeric task ID.

    Format: TSK-<9 alphanumeric chars> (e.g., "TSK-aB3dE5fG7")
    Used for task management.
    """
    return f"TSK-{generate_alphanumeric_id(9)}"


def generate_alert_id() -> str:
    """Generate a 12-character alphanumeric alert ID.

    Format: ALT-<9 alphanumeric chars> (e.g., "ALT-aB3dE5fG7")
    Used for system alerts/notifications.
    """
    return f"ALT-{generate_alphanumeric_id(9)}"


def generate_conversation_id() -> str:
    """Generate a 12-character alphanumeric conversation ID.

    Format: CNV-<9 alphanumeric chars> (e.g., "CNV-aB3dE5fG7")
    Used for chat conversations.
    """
    return f"CNV-{generate_alphanumeric_id(9)}"


def generate_report_id() -> str:
    """Generate a 12-character alphanumeric report ID.

    Format: RPT-<9 alphanumeric chars> (e.g., "RPT-aB3dE5fG7")
    Used for generated reports.
    """
    return f"RPT-{generate_alphanumeric_id(9)}"


def generate_water_quality_id() -> str:
    """Generate a 12-character alphanumeric water quality record ID.

    Format: WQR-<9 alphanumeric chars> (e.g., "WQR-aB3dE5fG7")
    Used for water quality measurements.
    """
    return f"WQR-{generate_alphanumeric_id(9)}"


def generate_feeding_id() -> str:
    """Generate a 12-character alphanumeric feeding record ID.

    Format: FED-<9 alphanumeric chars> (e.g., "FED-aB3dE5fG7")
    Used for feeding records.
    """
    return f"FED-{generate_alphanumeric_id(9)}"


# Unique key validation helpers
def ensure_unique_account_key() -> str:
    """Generate a unique account key, checking against existing records."""
    try:
        accounts_coll = get_collection('users')
        coll = getattr(accounts_coll, 'collection', accounts_coll)
        while True:
            key = generate_account_key()
            if not coll.find_one({'account_key': key}):
                return key
    except Exception:
        return generate_account_key()


def ensure_unique_user_key() -> str:
    """Generate a unique user key, checking against existing records."""
    try:
        users_coll = get_collection('users')
        coll = getattr(users_coll, 'collection', users_coll)
        while True:
            key = generate_user_key()
            if not coll.find_one({'user_key': key}):
                return key
    except Exception:
        return generate_user_key()


def epoch_to_datetime(epoch):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch))

def get_current_timestamp():
    """Return current timestamp as ISO string (UTC-aware using time util)."""
    try:
        return get_time_date_dt(include_time=True).isoformat()
    except Exception:
        return time.strftime('%Y-%m-%dT%H:%M:%S')


def generate_sampling_id():
    """Generate a sampling id of the form SAMP-<YYYYmmddHHMMSS>-<rand4>."""
    ts = get_time_date_dt(include_time=True).strftime('%Y%m%d%H%M%S')
    return f"SAMP-{ts}-{random.randint(1000,9999)}"


def generate_stock_id(sampling_id: str = None) -> str:
    """Generate a stable stock id.

    - If a sampling_id is provided, prefer the form `stock-<sampling_id>` so callers can
      easily link stock entries to samplings.
    - Otherwise generate a timestamped id with microseconds for uniqueness.
    """
    if sampling_id:
        # sanitize sampling_id to a short form if needed
        s = str(sampling_id)
        return f"stock-{s}"
    ts = get_time_date_dt(include_time=True).strftime('%Y%m%d%H%M%S%f')
    return f"stock-{ts}-{random.randint(100,999)}"


def derive_stock_id_from_dto(dto: dict) -> str:
    """Try to extract a stock_id from a DTO-like object or build one using sampling ids.

    Accepts either a dict-like or an object with `extra`/`id` attributes.
    """
    # Try explicit extra.stock_id first
    try:
        extra = None
        if isinstance(dto, dict):
            extra = dto.get('extra') or {}
            sid = dto.get('id') or dto.get('sampling_id')
        else:
            extra = getattr(dto, 'extra', None) or {}
            sid = getattr(dto, 'id', None) or getattr(dto, 'sampling_id', None)
        if isinstance(extra, dict) and extra.get('stock_id'):
            return str(extra.get('stock_id'))
        if sid:
            return generate_stock_id(str(sid))
    except Exception:
        pass
    # fallback
    return generate_stock_id()


def build_user(data, account_key=None):
    user_data = data.copy()
    user_data['account_key'] = account_key if account_key else ensure_unique_account_key()
    # If account_key is provided, try to fetch admin's subscription
    admin_subscription = None
    if account_key:
        admin_doc = user_repo.find_one({
            'account_key': account_key,
            'roles': {'$in': ['admin']}
        })
        if admin_doc and 'subscription' in admin_doc:
            admin_subscription = admin_doc['subscription']
    # Use the new unique user key generator
    user_data['user_key'] = ensure_unique_user_key()
    # Set permission level based on role
    roles = user_data.get('roles', ['user'])
    if isinstance(roles, str):
        roles = [roles]
    if 'admin' in roles:
        # Require company_name for admin
        company_name = user_data.get('company_name')
        if not company_name:
            raise ValueError('company_name is required for admin signup')
        user_data['company_name'] = company_name
        user_data['permission'] = {'level': 'admin', 'granted': True}
    else:
        user_data['permission'] = {'level': 'user', 'granted': True}
    user_data['joined_date'] = get_current_timestamp()
    # Use admin's subscription if available, else default
    user_data['subscription'] = admin_subscription if admin_subscription else default_subscription()
    if 'password' in user_data:
        user_data['password'] = base64.b64encode(user_data['password'].encode('utf-8')).decode('utf-8')
    refresh_payload = {
        'user_key': user_data['user_key'],
        'account_key': user_data['account_key'],
        'permission': user_data['permission'],
        'roles': user_data.get('roles', ['user']),
        'type': 'refresh'
    }
    refresh_token = AuthSecurity.create_refresh_token(refresh_payload)
    user_data['refresh_tokens'] = [refresh_token]
    return user_data


def build_refresh(user_data):
    refresh_payload = {
        'user_key': user_data['user_key'],
        'account_key': user_data['account_key'],
        'permission': user_data['permission'],
        'roles': user_data.get('roles', []),
        'type': 'refresh'
    }
    refresh_token = AuthSecurity.create_refresh_token(refresh_payload)
    return refresh_token


def resolve_user(identifier, account_key):
    """Find user by userkey, email, phone, username, or name within the given account."""
    query_fields = ['user_key', 'email', 'phone', 'username', 'name']
    for field in query_fields:
        user = user_repo.find_one({field: identifier, 'account_key': account_key})
        if user:
            return user
    return None


def get_default_task_date(current_time=None):
    """Return current date as YYYY-MM-DD."""
    if current_time is None:
        current_time = time.time()
    return time.strftime('%Y-%m-%d', time.localtime(current_time))


def get_default_end_date(current_time=None):
    """Return date 24 hours from current_time as YYYY-MM-DD."""
    if current_time is None:
        current_time = time.time()
    end_epoch = int(current_time) + 86400
    return time.strftime('%Y-%m-%d', time.localtime(end_epoch))

# Re-export get_time_date for callers that import it from this module
get_time_date = _get_time_date


def generate_account_number(ifsc: str = '572137') -> str:
    """Generate a 12-digit account number starting with the given IFSC prefix.

    Format: <ifsc><6-digit sequential suffix> e.g. 572137000001
    The function finds the highest existing suffix in `bank_accounts.account_number`
    that starts with the given IFSC and increments it. If none found, it starts
    at 000000. This keeps account numbers incremental rather than random.

    NOTE: This function is idempotent and best-effort in presence of concurrent
    calls; for full transactional guarantees use a DB sequence collection or
    transactions. For now this heuristic meets the immediate requirement.
    """
    # Normalize IFSC to digits only and ensure length 6
    ifsc_digits = re.sub(r'\D', '', str(ifsc))[:6].ljust(6, '0')
    try:
        # Try to access bank_accounts collection via get_collection
        bank_accounts = get_collection('bank_accounts')
        coll = getattr(bank_accounts, 'collection', bank_accounts)
        # Find account_numbers that start with the IFSC prefix
        cursor = coll.find({'account_number': {'$regex': f'^{ifsc_digits}'}}, {'account_number': 1})
        max_suffix = -1
        for doc in cursor:
            an = str(doc.get('account_number') or '')
            # extract trailing digits
            m = re.search(r'(\d+)$', an)
            if m:
                digits = m.group(1)
                # consider only last 6 digits as suffix
                s = digits[-6:]
                try:
                    val = int(s)
                    if val > max_suffix:
                        max_suffix = val
                except Exception:
                    continue
        next_suffix = 0 if max_suffix < 0 else (max_suffix + 1)
    except Exception:
        # If collection access fails, fall back to a process-local increment starting at 0
        # This is a safe fallback for tests or environments without DB access.
        try:
            # Use a simple attribute on the function to persist across calls
            if not hasattr(generate_account_number, '_local_counter'):
                generate_account_number._local_counter = 0
            generate_account_number._local_counter += 1
            next_suffix = generate_account_number._local_counter
        except Exception:
            next_suffix = 0
    # format suffix as 6 digits
    suffix_str = f"{next_suffix:06d}"
    return f"{ifsc_digits}{suffix_str}"
