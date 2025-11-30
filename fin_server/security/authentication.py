from jose import jwt, JWTError
from datetime import datetime, timedelta
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import hashlib
import time

class AuthSecurity:
    secret_key = None
    algorithm = 'HS256'
    access_token_expire_minutes = 60
    refresh_token_expire_days = 1

    def __init__(self, secret_key=None, algorithm='HS256', access_token_expire_minutes=60, refresh_token_expire_days=7):
        if secret_key:
            self.__class__.secret_key = secret_key
        self.__class__.algorithm = algorithm
        self.__class__.access_token_expire_minutes = access_token_expire_minutes
        self.__class__.refresh_token_expire_days = refresh_token_expire_days

    @classmethod
    def configure(cls, secret_key, algorithm='HS256', access_token_expire_minutes=60, refresh_token_expire_days=7):
        cls.secret_key = secret_key
        cls.algorithm = algorithm
        cls.access_token_expire_minutes = access_token_expire_minutes
        cls.refresh_token_expire_days = refresh_token_expire_days

    @classmethod
    def encode_token(cls, data: dict, expires_delta: timedelta = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=cls.access_token_expire_minutes))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, cls.secret_key, algorithm=cls.algorithm)

    @classmethod
    def decode_token(cls, token: str) -> dict:
        try:
            payload = jwt.decode(token, cls.secret_key, algorithms=[cls.algorithm])
            # Check expiry
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
                    raise ValueError("Token expired")
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid token: {str(e)}")
        except Exception as e:
            raise ValueError(f"Token decode error: {str(e)}")

    @classmethod
    def create_refresh_token(cls, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=cls.refresh_token_expire_days)
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
    def validate(cls, repository, collection_name, token: str) -> bool:
        try:
            payload = cls.decode_token(token)
            user_key = payload.get('user_key')
            account_key = payload.get('account_key')
            permission = payload.get('permission')
            user = repository.find_one(collection_name, {'user_key': user_key, 'account_key': account_key, 'permission': permission})
            return user is not None
        except Exception:
            return False

    @classmethod
    def validate_has_role(cls, token: str, required_roles) -> bool:
        try:
            payload = cls.decode_token(token)
            user_roles = payload.get('roles', [])
            if isinstance(required_roles, str):
                required_roles = [required_roles]
            return all(role in user_roles for role in required_roles)
        except Exception:
            return False

    @classmethod
    def validate_has_actions(cls, token: str, required_actions) -> bool:
        try:
            payload = cls.decode_token(token)
            user_actions = payload.get('actions', [])
            if isinstance(required_actions, str):
                required_actions = [required_actions]
            return all(action in user_actions for action in required_actions)
        except Exception:
            return False

    @classmethod
    def validate_refresh_token(cls, repository, collection_name, user_key: str, refresh_token: str) -> bool:
        try:
            payload = cls.decode_token(refresh_token)
            if payload.get('type') != 'refresh':
                return False
            user = repository.find_one(collection_name, {'user_key': user_key})
            tokens = user.get('refresh_tokens', [])[-5:] if user else []
            # Base validation: ensure the token belongs to the same user
            token_user_key = payload.get('user_key')
            if not token_user_key or token_user_key != user_key:
                return False
            return refresh_token in tokens
        except Exception:
            return False

    @classmethod
    def validate_role_token(cls, repository, collection_name, token: str, required_role: str, account_key: str = None) -> bool:
        try:
            payload = cls.decode_token(token)
            user_key = payload.get('user_key')
            query = {'user_key': user_key}
            if account_key:
                query['account_key'] = account_key
            user = repository.find_one(collection_name, query)
            if not user:
                return False
            user_roles = payload.get('roles', [])
            return required_role in user_roles
        except Exception:
            return False

    @classmethod
    def validate_roles_token(cls, repository, collection_name, token: str, required_roles: list, account_key: str = None) -> bool:
        try:
            payload = cls.decode_token(token)
            user_key = payload.get('user_key')
            query = {'user_key': user_key}
            if account_key:
                query['account_key'] = account_key
            user = repository.find_one(collection_name, query)
            if not user:
                return False
            # Use 'role' for single role, 'roles' for multiple roles
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
