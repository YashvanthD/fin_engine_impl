import base64
import random
import re
import time
import uuid

from fin_server.repository.mongo_helper import get_collection
from fin_server.requests.subscription import default_subscription
from fin_server.security.authentication import AuthSecurity
from fin_server.utils.time_utils import get_time_date_dt, get_time_date as _get_time_date

user_repo = get_collection('users')


def generate_key(
    length=24,
    include_alphabets=False,
    include_special=False,
    include_numbers=True,
    uppercase_only=False,
    lowercase_only=False,
    uuid_format=True
):
    """Generate a random key of the requested length.

    By default, generates a 24-character UUID-like hex string (e.g., '69653c8af4c2d41e5a1bcdbd').

    Args:
        length: Length of the generated key (default: 24)
        include_alphabets: Include letters (A-Z, a-z)
        include_special: Include special characters (!@#$%^&*()-_=+)
        include_numbers: Include digits (0-9)
        uppercase_only: Only uppercase letters (when include_alphabets=True)
        lowercase_only: Only lowercase letters (when include_alphabets=True)
        uuid_format: If True, generates a UUID-based hex string (default: True)

    Returns:
        Random string of specified length

    Raises:
        ValueError: If no character set is selected (when uuid_format=False)
    """
    # Default: Generate UUID-like hex string
    if uuid_format:
        # Generate a UUID and convert to hex string (no dashes)
        # uuid4 gives 32 hex chars, we can truncate or extend as needed
        hex_str = uuid.uuid4().hex
        if length <= 32:
            return hex_str[:length]
        else:
            # For longer lengths, concatenate multiple UUIDs
            result = hex_str
            while len(result) < length:
                result += uuid.uuid4().hex
            return result[:length]

    # Legacy behavior: custom character set
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
# ID Format Standards (Updated: January 13, 2026):
#   - account_key:      12 numeric digits (e.g., "123456789012")
#   - user_key:         12 numeric digits (e.g., "987654321098")
#   - message_id:       24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - transaction_id:   24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - expense_id:       24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - pond_id:          24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - pond_event_id:    24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - fish_event_id:    24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - batch_id:         24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - sampling_id:      24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - species_code:     24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - account_number:   12 numeric digits (e.g., "572137000001")
#   - task_id:          24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - conversation_id:  24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - feed_id:          24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
#   - stock_id:         24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
# ============================================================================


def generate_uuid_hex(length: int = 24) -> str:
    """Generate a UUID-based hex string.

    Args:
        length: Length of hex string (default: 24)

    Returns:
        Lowercase hex string (e.g., '69653c8af4c2d41e5a1bcdbd')
    """
    return generate_key(length=length, uuid_format=True)


def generate_account_key() -> str:
    """Generate a 12-digit numeric account key.

    Format: 12 numeric digits (e.g., "123456789012")
    Used to identify an organization/company.
    """
    return generate_key(length=12, uuid_format=False, include_numbers=True, include_alphabets=False)


def generate_user_key() -> str:
    """Generate a 12-digit numeric user key.

    Format: 12 numeric digits (e.g., "987654321098")
    Used to identify individual users within the system.
    """
    return generate_key(length=12, uuid_format=False, include_numbers=True, include_alphabets=False)


def generate_alphanumeric_id(length=24) -> str:
    """Generate a UUID-based hex ID of specified length.

    Format: Lowercase hex characters (0-9, a-f)
    Base generator for various ID types.

    Args:
        length: Length of hex string (default: 24)

    Returns:
        UUID hex string (e.g., '69653c8af4c2d41e5a1bcdbd')
    """
    return generate_uuid_hex(length=length)


def generate_message_id() -> str:
    """Generate a UUID-based message ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for chat/messaging system.
    """
    return generate_uuid_hex(24)


def generate_transaction_id() -> str:
    """Generate a UUID-based transaction ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for financial transactions.
    """
    return generate_uuid_hex(24)


def generate_expense_id() -> str:
    """Generate a UUID-based expense ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for expense records.
    """
    return generate_uuid_hex(24)


def generate_pond_id(account_key: str = None) -> str:
    """Generate a UUID-based pond ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used to identify ponds.

    Args:
        account_key: Optional (kept for backward compatibility, not used)

    Returns:
        Pond ID as 24 hex chars
    """
    return generate_uuid_hex(24)


def generate_pond_event_id() -> str:
    """Generate a UUID-based pond event ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for pond-related events (stocking, transfer, harvest, etc.)
    """
    return generate_uuid_hex(24)


def generate_fish_event_id() -> str:
    """Generate a UUID-based fish event ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for fish-related events (mortality, growth, feeding, etc.)
    """
    return generate_uuid_hex(24)


def generate_batch_id() -> str:
    """Generate a UUID-based batch ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for fish batch tracking.
    """
    return generate_uuid_hex(24)


def generate_new_sampling_id() -> str:
    """Generate a UUID-based sampling ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for sampling/growth records.
    """
    return generate_uuid_hex(24)


def generate_species_code(name: str = None) -> str:
    """Generate a UUID-based species code.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")

    Args:
        name: Optional (kept for backward compatibility, not used)

    Returns:
        Species code as 24 hex chars
    """
    return generate_uuid_hex(24)


def generate_task_id() -> str:
    """Generate a UUID-based task ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for task management.
    """
    return generate_uuid_hex(24)


def generate_alert_id() -> str:
    """Generate a UUID-based alert ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for system alerts/notifications.
    """
    return generate_uuid_hex(24)


def generate_conversation_id() -> str:
    """Generate a UUID-based conversation ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for chat conversations.
    """
    return generate_uuid_hex(24)


def generate_report_id() -> str:
    """Generate a UUID-based report ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for generated reports.
    """
    return generate_uuid_hex(24)


def generate_water_quality_id() -> str:
    """Generate a UUID-based water quality record ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for water quality measurements.
    """
    return generate_uuid_hex(24)


def generate_feeding_id() -> str:
    """Generate a UUID-based feeding record ID.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for feeding records.
    """
    return generate_uuid_hex(24)


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
    """Generate a UUID-based sampling id.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")
    Used for sampling/growth records.
    """
    return generate_uuid_hex(24)


def generate_stock_id(sampling_id: str = None) -> str:
    """Generate a stable stock id using UUID format.

    Format: 24 hex chars (e.g., "69653c8af4c2d41e5a1bcdbd")

    Args:
        sampling_id: Optional - if provided, returns it as-is for linking purposes

    Returns:
        Stock ID as 24 hex chars
    """
    if sampling_id:
        return str(sampling_id)
    return generate_uuid_hex(24)


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


def get_user_subscription_from_admin(account_key: str):
    """Fetch subscription details for the given account key from an admin user."""
    try:
        admin_doc = user_repo.find_one({
            'account_key': account_key,
            'role': 'admin'
        })
        if admin_doc and 'subscription' in admin_doc:
            return {
                'subscription_type': admin_doc.get('subscription', {'subscription_type':"free"}).get('subscription_type'),
                'expiry': admin_doc.get('subscription',{"expiry":""}).get('expiry')}
    except Exception:
        pass




def build_user(data, account_key=None):
    user_data = data.copy()
    is_owner = True if account_key else False
    user_data['account_key'] = account_key if account_key else ensure_unique_account_key()
    # If account_key is provided, try to fetch admin's subscription
    # Use the new unique user key generator
    user_data['user_key'] = ensure_unique_user_key()


    # Role is a single string value
    role = user_data.get('role', 'admin' if is_owner else 'user')
    user_data['role'] = role

    # Authorities are special permissions granted beyond the role
    authorities = user_data.get('authorities', [])
    if not isinstance(authorities, list):
        authorities = []
    user_data['authorities'] = authorities

    # Set permission level based on role
    if role in ['admin', 'owner']:
        if role == 'admin':
            company_name = user_data.get('company_name')
            if not company_name:
                raise ValueError('company_name is required for admin signup')
            user_data['company_name'] = company_name
        user_data['permission'] = {'level': 'admin', 'granted': True}
    elif role == 'manager':
        user_data['permission'] = {'level': 'manager', 'granted': True}
    else:
        user_data['permission'] = {'level': 'user', 'granted': True}

    user_data['joined_date'] = get_current_timestamp()
    # Use admin's subscription if available, else default
    user_data['subscription'] = get_user_subscription_from_admin(account_key) if not is_owner else default_subscription()
    if 'password' in user_data:
        user_data['password'] = base64.b64encode(user_data['password'].encode('utf-8')).decode('utf-8')
    refresh_payload = {
        'user_key': user_data['user_key'],
        'account_key': user_data['account_key'],
        'permission': user_data['permission'],
        'role': user_data['role'],
        'authorities': user_data['authorities'],
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
        'role': user_data.get('role', 'user'),
        'authorities': user_data.get('authorities', []),
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
