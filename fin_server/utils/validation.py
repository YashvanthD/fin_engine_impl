def validate_user_signup(data, account_key):
    errors = {}
    # account_key must be present and not null
    if not account_key or not str(account_key).strip():
        errors['account_key'] = 'Account key is required.'
    # roles must be present and not null
    roles = data.get('roles')
    if not roles:
        errors['roles'] = 'Roles are required.'
    # actions default to [] if not present
    actions = data.get('actions')
    if actions is None:
        data['actions'] = []
    return (len(errors) == 0, errors)

def validate_signup(data):
    errors = {}
    if not data.get('username') or not str(data.get('username')).strip():
        errors['username'] = 'Username is required.'
    email = data.get('email')
    phone = data.get('phone')
    if not (email and str(email).strip()) and not (phone and str(phone).strip()):
        errors['email_or_phone'] = 'Either email or phone is required.'
    if not data.get('password') or not str(data.get('password')).strip():
        errors['password'] = 'Password is required.'
    return (len(errors) == 0, errors)

def validate_signup_user(data, account_key):
    errors = {}
    if not data.get('username') or not str(data.get('username')).strip():
        errors['username'] = 'Username is required.'
    email = data.get('email')
    phone = data.get('phone')
    if not (email and str(email).strip()) and not (phone and str(phone).strip()):
        errors['email_or_phone'] = 'Either email or phone is required.'
    if not data.get('password') or not str(data.get('password')).strip():
        errors['password'] = 'Password is required.'
    if not account_key or not str(account_key).strip():
        errors['account_key'] = 'Account key is required.'
    roles = data.get('roles')
    if not roles:
        errors['roles'] = 'Roles are required.'
    actions = data.get('actions')
    if actions is None:
        data['actions'] = []
    return (len(errors) == 0, errors)


def build_signup_login_response(success, message, user_id, account_key, user_key):
    """Standardize signup/login response shape across auth/company routes.

    This lives in validation so that multiple routes can reuse it without
    re-implementing the response structure.
    """
    return {
        'success': success,
        'message': message,
        'user_id': str(user_id),
        'account_key': account_key,
        'user_key': user_key,
    }


def _is_int(v):
    try:
        int(v)
        return True
    except Exception:
        return False


def validate_pond_event_payload(data, event_type):
    """Validate payload for pond_event actions.
    Returns (ok: bool, errors: dict)
    """
    errors = {}
    fish_id = data.get('fish_id')
    count = data.get('count')

    if not fish_id or not str(fish_id).strip():
        errors['fish_id'] = 'fish_id is required.'
    if count is None or not _is_int(count) or int(count) <= 0:
        errors['count'] = 'count is required and must be a positive integer.'

    if event_type in ['add', 'shift_in']:
        fam = data.get('fish_age_in_month')
        if fam is None or not _is_int(fam) or int(fam) < 0:
            errors['fish_age_in_month'] = 'fish_age_in_month is required for add/shift_in and must be a non-negative integer.'

    # samples if present should be a list of dicts
    samples = data.get('samples')
    if samples is not None:
        if not isinstance(samples, list):
            errors['samples'] = 'samples must be an array of measurement objects.'
        else:
            for i, s in enumerate(samples):
                if not isinstance(s, dict):
                    errors[f'samples[{i}]'] = 'each sample must be an object/dict.'

    return (len(errors) == 0, errors)


def validate_fish_create(data):
    errors = {}
    # require at least one of common_name or scientific_name
    com = data.get('common_name')
    sci = data.get('scientific_name')
    if not (com and str(com).strip()) and not (sci and str(sci).strip()):
        errors['common_or_scientific_name'] = 'Either common_name or scientific_name is required.'
    return (len(errors) == 0, errors)


def validate_batch_add(data):
    errors = {}
    if not data.get('species_code'):
        errors['species_code'] = 'species_code is required.'
    count = data.get('count')
    if count is None or not _is_int(count) or int(count) <= 0:
        errors['count'] = 'count is required and must be a positive integer.'
    fam = data.get('fish_age_in_month')
    if fam is None or not _is_int(fam) or int(fam) < 0:
        errors['fish_age_in_month'] = 'fish_age_in_month is required and must be a non-negative integer.'
    return (len(errors) == 0, errors)


def validate_fish_update_payload(data):
    errors = {}
    # If adding a batch via update, both count and fish_age_in_month must be present
    if 'count' in data or 'fish_age_in_month' in data:
        if 'count' not in data or 'fish_age_in_month' not in data:
            errors['batch'] = 'Both count and fish_age_in_month must be provided together to add a batch.'
        else:
            if not _is_int(data.get('count')) or int(data.get('count')) <= 0:
                errors['count'] = 'count must be a positive integer.'
            if not _is_int(data.get('fish_age_in_month')) or int(data.get('fish_age_in_month')) < 0:
                errors['fish_age_in_month'] = 'fish_age_in_month must be a non-negative integer.'
    return (len(errors) == 0, errors)


def validate_pagination_params(args):
    errors = {}
    try:
        limit = int(args.get('limit', 100))
        if limit < 1 or limit > 1000:
            errors['limit'] = 'limit must be between 1 and 1000'
    except Exception:
        errors['limit'] = 'limit must be an integer'
    try:
        skip = int(args.get('skip', 0))
        if skip < 0:
            errors['skip'] = 'skip must be >= 0'
    except Exception:
        errors['skip'] = 'skip must be an integer'
    return (len(errors) == 0, errors)
