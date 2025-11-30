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
