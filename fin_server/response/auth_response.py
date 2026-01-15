def build_user_response(user_dto, access_token=None, refresh_token=None):
    response = {
        'success': True,
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'role': user_dto.role,
        'authorities': user_dto.authorities,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription
    }
    if access_token:
        response['access_token'] = access_token
    if refresh_token:
        response['refresh_token'] = refresh_token
    return response

def build_token_only_response(access_token, expires_in=None):
    response = {
        'access_token': access_token
    }
    if expires_in:
        response['expires_in'] = expires_in
    return response

def build_signup_login_response(success, message, user_id, account_key, user_key):
    return {
        'success': success,
        'message': message,
        'user_id': user_id,
        'account_key': account_key,
        'user_key': user_key
    }
