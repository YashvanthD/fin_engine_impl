import time
import random
import base64

from fin_server.repository.mongo_helper import MongoRepositorySingleton
repo = MongoRepositorySingleton.get_instance()
user_repo = repo.user

from fin_server.security.authentication import AuthSecurity

def epoch_to_datetime(epoch):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch))

def get_current_timestamp():
    return int(time.time())

def generate_key(length):
    return ''.join(random.choices('0123456789', k=length))

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
