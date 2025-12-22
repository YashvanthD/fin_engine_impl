from jose import jwt, JWTError
from datetime import timedelta, datetime
from fin_server.utils.time_utils import get_time_date_dt, now_std
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import hashlib
import time
from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.repository.mongo_helper import MongoRepositorySingleton

class AuthSecurity:
    secret_key = None
    algorithm = 'HS256'
    # Defaults: access token valid for 7 days, refresh token valid for 90 days
    access_token_expire_minutes = 7 * 24 * 60  # 10080 minutes
    refresh_token_expire_days = 90

    def __init__(self, secret_key=None, algorithm='HS256', access_token_expire_minutes=7*24*60, refresh_token_expire_days=90):
        if secret_key:
            self.__class__.secret_key = secret_key
        self.__class__.algorithm = algorithm
        self.__class__.access_token_expire_minutes = access_token_expire_minutes
        self.__class__.refresh_token_expire_days = refresh_token_expire_days

    @classmethod
    def configure(cls, secret_key, algorithm='HS256', access_token_expire_minutes=7*24*60, refresh_token_expire_days=90):
        cls.secret_key = secret_key
        cls.algorithm = algorithm
        cls.access_token_expire_minutes = access_token_expire_minutes
        cls.refresh_token_expire_days = refresh_token_expire_days

    @classmethod
    def encode_token(cls, data: dict, expires_delta: timedelta = None) -> str:
        to_encode = data.copy()
        # Derive base time from now_std (IST by default) and add expiry delta.
        base = now_std(include_time=True)
        expire = base + (expires_delta or timedelta(minutes=cls.access_token_expire_minutes))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, cls.secret_key, algorithm=cls.algorithm)

    @classmethod
    def decode_token(cls, token: str) -> dict:
        # Check for well-formed JWT (should have 2 dots)
        if not token or token.count('.') != 2:
            raise UnauthorizedError("Malformed or missing token. Please provide a valid JWT token in the Authorization header.")
        try:
            payload = jwt.decode(token, cls.secret_key, algorithms=[cls.algorithm])
            exp = payload.get('exp')
            if exp is not None:
                now = int(time.time())
                if isinstance(exp, datetime):
                    exp = int(exp.timestamp())
                elif isinstance(exp, float):
                    exp = int(exp)
                elif isinstance(exp, str):
                    exp = int(float(exp))
                if exp < now:
                    raise UnauthorizedError("Token expired. Please login again or refresh your session.")
            return payload
        except JWTError as e:
            msg = str(e)
            if 'Signature has expired' in msg:
                raise UnauthorizedError("Token expired. Please login again or refresh your session.")
            elif 'Not enough segments' in msg or 'Invalid header string' in msg:
                raise UnauthorizedError("Malformed or missing token. Please provide a valid JWT token in the Authorization header.")
            elif 'Signature verification failed' in msg:
                raise UnauthorizedError("Invalid token signature. Please login again or contact support if the problem persists.")
            else:
                raise UnauthorizedError(f"Invalid token: {msg}. Please check your authentication and try again.")
        except Exception as e:
            raise UnauthorizedError(f"Token decode error: {str(e)}. Please contact support if this persists.")

    @classmethod
    def create_refresh_token(cls, data: dict) -> str:
        to_encode = data.copy()
        base = now_std(include_time=True)
        expire = base + timedelta(days=cls.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, cls.secret_key, algorithm=cls.algorithm)

    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> str:
        try:
            payload = jwt.decode(refresh_token, cls.secret_key, algorithms=[cls.algorithm])
            if payload.get("type") != "refresh":
                raise ValueError("Invalid refresh token type.")
            # Remove exp and type for new access token
            payload.pop("exp", None)
            payload.pop("type", None)
            return cls.encode_token(payload)
        except JWTError as e:
            raise ValueError(f"Invalid refresh token: {str(e)}")

    @staticmethod
    def encode_base64(data: bytes) -> str:
        return base64.b64encode(data).decode('utf-8')

    @staticmethod
    def decode_base64(data: str) -> bytes:
        return base64.b64decode(data.encode('utf-8'))

    @staticmethod
    def generate_rsa_key_pair(key_size=2048):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return private_pem, public_pem

    @staticmethod
    def hash_key(key: bytes) -> str:
        return hashlib.sha256(key).hexdigest()

    @staticmethod
    def validate_key_hash(key: bytes, key_hash: str) -> bool:
        return AuthSecurity.hash_key(key) == key_hash

    @staticmethod
    def check_private_public_match(private_pem: bytes, public_pem: bytes) -> bool:
        try:
            private_key = serialization.load_pem_private_key(private_pem, password=None, backend=default_backend())
            public_key = serialization.load_pem_public_key(public_pem, backend=default_backend())
            return private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ) == public_pem
        except Exception:
            return False

    @classmethod
    def _user_repo(cls):
        """Convenience accessor for the UserRepository singleton."""
        return MongoRepositorySingleton.get_instance().user

    @classmethod
    def validate(cls, repository, collection_name, token: str) -> bool:
        """Legacy validate API kept for compatibility.

        New code should prefer validate_token_for_account(), which uses
        the UserRepository directly. This implementation now delegates
        to _user_repo() and ignores the injected repository/collection_name.
        """
        try:
            payload = cls.decode_token(token)
            user_key = payload.get('user_key')
            account_key = payload.get('account_key')
            permission = payload.get('permission')
            repo = cls._user_repo()
            user = repo.find_one({'user_key': user_key, 'account_key': account_key, 'permission': permission})
            return user is not None
        except Exception:
            return False

    @classmethod
    def validate_refresh_token(cls, repository, collection_name, user_key: str, refresh_token: str) -> bool:
        """Validate a refresh token for a given user_key.

        The repository/collection_name parameters are ignored; we always
        use the UserRepository singleton under the hood.
        """
        try:
            payload = cls.decode_token(refresh_token)
            if payload.get('type') != 'refresh':
                return False
            repo = cls._user_repo()
            user = repo.find_one({'user_key': user_key})
            tokens = user.get('refresh_tokens', [])[-5:] if user else []
            token_user_key = payload.get('user_key')
            if not token_user_key or token_user_key != user_key:
                return False
            return refresh_token in tokens
        except Exception:
            return False

    @classmethod
    def validate_role_token(cls, repository, collection_name, token: str, required_role: str, account_key: str = None) -> bool:
        """Validate that the token belongs to a user with a specific role.

        Uses the UserRepository directly; repository and collection_name
        are accepted for backwards compatibility but ignored.
        """
        try:
            payload = cls.decode_token(token)
            user_key = payload.get('user_key')
            query = {'user_key': user_key}
            if account_key:
                query['account_key'] = account_key
            repo = cls._user_repo()
            user = repo.find_one(query)
            print("user found for role validation:", user, query)
            if not user:
                return False
            user_roles = payload.get('roles', [])
            return required_role in user_roles
        except Exception:
            return False

    @classmethod
    def validate_roles_token(cls, repository, collection_name, token: str, required_roles: list, account_key: str = None) -> bool:
        """Validate that the token has all of the required roles.

        Uses the UserRepository directly; repository and collection_name
        are accepted for backwards compatibility but ignored.
        """
        try:
            payload = cls.decode_token(token)
            user_key = payload.get('user_key')
            query = {'user_key': user_key}
            if account_key:
                query['account_key'] = account_key
            repo = cls._user_repo()
            user = repo.find_one(query)
            if not user:
                return False
            user_roles = []
            if 'roles' in payload:
                user_roles = payload.get('roles', [])
            elif 'role' in payload:
                user_roles = [payload.get('role')]
            if isinstance(required_roles, str):
                required_roles = [required_roles]
            return all(role in user_roles for role in required_roles)
        except Exception:
            return False

    @classmethod
    def validate_token_for_account(cls, token: str, account_key: str = None) -> bool:
        """New helper: validate a token against the current UserRepository and optional account_key."""
        try:
            payload = cls.decode_token(token)
            user_key = payload.get('user_key')
            query = {'user_key': user_key}
            if account_key:
                query['account_key'] = account_key
            repo = cls._user_repo()
            user = repo.find_one(query)
            return user is not None
        except Exception:
            return False

    @classmethod
    def validate_and_cleanup_refresh_tokens(cls, user_dto, create_new=True):
        now = int(time.time())
        valid_tokens = []
        for token in user_dto.refresh_tokens:
            try:
                payload = cls.decode_token(token)
                exp = int(payload.get('exp', 0))
                if exp > now:
                    valid_tokens.append(token)
            except Exception:
                continue
        user_dto._refresh_tokens = valid_tokens
        user_dto._refresh_token_cache = set(valid_tokens)
        if not valid_tokens:
            return False, None  # Force re-login
        new_refresh_token = None
        if create_new:
            refresh_payload = {
                'user_key': user_dto.user_key,
                'account_key': user_dto.account_key,
                'roles': user_dto.roles,
                'type': 'refresh'
            }
            new_refresh_token = cls.create_refresh_token(refresh_payload)
            user_dto.add_refresh_token(new_refresh_token)
        return True, new_refresh_token

    @classmethod
    def decode_any_token(cls, token: str) -> dict:
        """
        Accepts either access_token or refresh_token and returns payload if valid.
        """
        if not token or token.count('.') != 2:
            raise UnauthorizedError("Malformed or missing token. Please provide a valid JWT token in the Authorization header.")
        try:
            payload = jwt.decode(token, AuthSecurity.secret_key, algorithms=[AuthSecurity.algorithm])
            exp = payload.get('exp')
            if exp is not None:
                now = int(time.time())
                if isinstance(exp, datetime):
                    exp = int(exp.timestamp())
                elif isinstance(exp, float):
                    exp = int(exp)
                elif isinstance(exp, str):
                    exp = int(float(exp))
                if exp < now:
                    raise UnauthorizedError("Token expired. Please login again or refresh your session.")
            # Accept both access and refresh tokens
            if payload.get('type') not in [None, 'access', 'refresh']:
                raise UnauthorizedError("Invalid token type.")
            return payload
        except JWTError as e:
            msg = str(e)
            if 'Signature has expired' in msg:
                raise UnauthorizedError("Token expired. Please login again or refresh your session.")
            elif 'Not enough segments' in msg or 'Invalid header string' in msg:
                raise UnauthorizedError("Malformed or missing token. Please provide a valid JWT token in the Authorization header.")
            elif 'Signature verification failed' in msg:
                raise UnauthorizedError("Invalid token signature. Please login again or contact support if the problem persists.")
            else:
                raise UnauthorizedError(f"Invalid token: {msg}. Please check your authentication and try again.")
        except Exception as e:
            raise UnauthorizedError(f"Token decode error: {str(e)}. Please contact support if this persists.")

def get_auth_payload(request):
    """
    Extracts and decodes the Bearer token from the Authorization header in the request.
    Raises UnauthorizedError if missing or invalid.
    Returns the decoded payload.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise UnauthorizedError('Missing or invalid token')
    token = auth_header.split(' ', 1)[1]
    return AuthSecurity.decode_token(token)
