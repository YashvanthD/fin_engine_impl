import base64
import random
import time

from fin_server.repository.mongo_helper import get_collection
from fin_server.requests.subscription import default_subscription
from fin_server.security.authentication import AuthSecurity
from fin_server.utils.time_utils import get_time_date_dt, get_time_date as _get_time_date

user_repo = get_collection('users')


def generate_key(length=6):
    """Generate a short alphanumeric key of the requested length."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(alphabet) for _ in range(int(length)))


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


def build_user(data, account_key=None):
    user_data = data.copy()
    user_data['account_key'] = account_key if account_key else generate_key(6)
    # If account_key is provided, try to fetch admin's subscription
    admin_subscription = None
    if account_key:
        admin_doc = user_repo.find_one({
            'account_key': account_key,
            'roles': {'$in': ['admin']}
        })
        if admin_doc and 'subscription' in admin_doc:
            admin_subscription = admin_doc['subscription']
    while True:
        user_key = generate_key(9)
        if not user_repo.find_one({'user_key': user_key}):
            break
    user_data['user_key'] = user_key
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
