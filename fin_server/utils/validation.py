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

    # Validate role - must be a string
    role = data.get('role')
    if not role:
        errors['role'] = 'Role is required.'
    else:
        # Validate role exists in defaults
        try:
            from config.defaults import defaults
            valid_roles = [r.get('role_code') for r in defaults.get_roles()]
            if role not in valid_roles:
                errors['role'] = f"Invalid role: {role}. Valid roles: {', '.join(valid_roles)}"
        except Exception:
            pass

    # Validate authorities (optional) - array of special permissions
    authorities = data.get('authorities')
    if authorities is not None:
        if not isinstance(authorities, list):
            errors['authorities'] = 'Authorities must be an array of permission codes.'
        else:
            # Validate each authority exists
            try:
                from config.defaults import defaults
                valid_permissions = [p.get('code') for p in defaults.get_permissions()]
                invalid_auths = [a for a in authorities if a not in valid_permissions]
                if invalid_auths:
                    errors['authorities'] = f"Invalid authorities: {', '.join(invalid_auths)}"
            except Exception:
                pass
    else:
        data['authorities'] = []

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


# New functions added to support sampling route behavior and tests

def is_buy_transaction(extra, dto=None):
    """Determine whether a transaction payload/extra indicates a buy (purchase).

    Returns (is_buy: bool, buy_count: int|None)
    Logic (defensive):
    - Look for transaction-type fields (transactionType, transaction, type) and check if value contains 'buy' (case-insensitive).
    - If any numeric buy count fields exist (buy_count, bought, count, quantity), parse and return as int.
    - If transaction indicates buy but no explicit count, fall back to dto.sampleSize or dto.sample_size when available.
    """
    try:
        if not isinstance(extra, dict):
            return (False, None)
        # Normalize keys
        tx_keys = ['transactionType', 'transaction', 'type', 'transaction_type', 'tx_type']
        tx_val = None
        for k in tx_keys:
            if k in extra and extra.get(k) is not None:
                tx_val = str(extra.get(k))
                break
        is_buy = False
        if tx_val:
            if 'buy' in tx_val.lower() or 'purchase' in tx_val.lower():
                is_buy = True
        # Also if extra contains explicit buy_count-like fields consider it a buy
        count_keys = ['buy_count', 'bought', 'count', 'quantity']
        buy_count = None
        for ck in count_keys:
            if ck in extra and extra.get(ck) is not None:
                try:
                    buy_count = int(float(extra.get(ck)))
                    is_buy = True
                    break
                except Exception:
                    continue
        # If we detected buy via tx_val but didn't find count, try dto.sampleSize
        if is_buy and buy_count is None and dto is not None:
            for attr in ('sampleSize', 'sample_size', 'sampleSize'):
                val = getattr(dto, attr, None)
                if val is not None:
                    try:
                        buy_count = int(float(val))
                        break
                    except Exception:
                        continue
        return (is_buy, buy_count)
    except Exception:
        return (False, None)


def compute_total_amount_from_payload(data, dto=None):
    """Compute a total monetary amount from request payload and DTO.

    Rules used by tests and route logic:
    - If explicit totalAmount / total_amount is present in data, parse and return rounded to 2 decimals.
    - Otherwise, if a per-unit cost is available (dto.cost or data.cost) and a sample/count exists (dto.sampleSize or sample_size), compute:
        total = unit_cost * weight_factor * count
      where weight_factor is determined by data.minWeight / min_weight or dto.averageWeight (clamped to >= 1.0), default 1.0.
    - Returns a float rounded to 2 decimals or None when insufficient data.
    """
    try:
        if not isinstance(data, dict):
            return None
        # explicit total
        if 'totalAmount' in data and data.get('totalAmount') is not None:
            try:
                return round(float(data.get('totalAmount')), 2)
            except Exception:
                pass
        if 'total_amount' in data and data.get('total_amount') is not None:
            try:
                return round(float(data.get('total_amount')), 2)
            except Exception:
                pass

        # find unit cost
        unit_cost = None
        if dto is not None and getattr(dto, 'cost', None) is not None:
            try:
                unit_cost = float(getattr(dto, 'cost'))
            except Exception:
                unit_cost = None
        if unit_cost is None and data.get('cost') is not None:
            try:
                unit_cost = float(data.get('cost'))
            except Exception:
                unit_cost = None

        # find count/sample size
        count = None
        if dto is not None:
            for attr in ('sampleSize', 'sample_size'):
                val = getattr(dto, attr, None)
                if val is not None:
                    try:
                        count = int(float(val))
                        break
                    except Exception:
                        continue
        if count is None:
            for k in ('sampleSize', 'sample_size', 'count', 'quantity'):
                if k in data and data.get(k) is not None:
                    try:
                        count = int(float(data.get(k)))
                        break
                    except Exception:
                        continue

        if unit_cost is None or count is None:
            return None

        # determine weight factor
        weight = None
        if 'minWeight' in data and data.get('minWeight') is not None:
            try:
                weight = float(data.get('minWeight'))
            except Exception:
                weight = None
        elif 'min_weight' in data and data.get('min_weight') is not None:
            try:
                weight = float(data.get('min_weight'))
            except Exception:
                weight = None
        elif dto is not None and getattr(dto, 'averageWeight', None) is not None:
            try:
                weight = float(getattr(dto, 'averageWeight'))
            except Exception:
                weight = None
        # default weight factor
        if weight is None:
            weight = 1.0
        # clamp averageWeight < 1 to 1.0 as tests expect
        try:
            if float(weight) < 1.0:
                weight = 1.0
        except Exception:
            weight = 1.0

        total = float(unit_cost) * float(weight) * int(count)
        return round(total, 2)
    except Exception:
        return None
