import time
from fin_server.repository.mongo_helper import MongoRepositorySingleton

repo = MongoRepositorySingleton.get_instance()
user_repo = repo.user

class UserDTO:
    # Class-level cache: user_key -> UserDTO
    _cache = {}
    _CACHE_EXPIRY_SECONDS = 86400  # 1 day

    def __init__(self, user_id, account_key, user_key, roles=None, refresh_tokens=None, settings=None, subscription=None, password=None, **kwargs):
        self.user_id = user_id
        self.account_key = account_key
        self.user_key = user_key
        self.roles = roles or []
        self._refresh_tokens = refresh_tokens or []
        self._refresh_token_cache = set(self._refresh_tokens)
        self.settings = settings or {}
        self.subscription = subscription or {}
        self.password = password
        self._extra_fields = kwargs
        self._last_activity = int(time.time())
        # Add to cache
        UserDTO._cache[self.user_key] = self

        # Add timezone to settings if not present
        if 'timezone' not in self.settings:
            self.settings['timezone'] = 'Asia/Kolkata'  # Default to IST

    def touch(self):
        self._last_activity = int(time.time())

    def add_refresh_token(self, token):
        self._refresh_tokens.append(token)
        self._refresh_token_cache.add(token)
        if len(self._refresh_tokens) > 5:
            self._refresh_tokens = self._refresh_tokens[-5:]
            self._refresh_token_cache = set(self._refresh_tokens)
        self.touch()

    def has_refresh_token(self, token):
        self.touch()
        return token in self._refresh_token_cache

    @property
    def refresh_tokens(self):
        self.touch()
        return self._refresh_tokens

    @property
    def last_active(self):
        return int(self._last_activity)

    def to_dict(self):
        self.touch()
        base = {
            'user_id': str(self.user_id) if self.user_id is not None else None,
            'account_key': self.account_key,
            'user_key': self.user_key,
            'roles': self.roles,
            'refresh_tokens': self._refresh_tokens,
            'last_update': int(self._last_activity),
            'last_active': int(self._last_activity),
            'settings': self.settings,
            'subscription': self.subscription,
            'profile': getattr(self, 'profile', {}),
            'password': self.password
        }
        # Ensure all extra fields are snake_case and ObjectId-safe
        for k, v in self._extra_fields.items():
            if k == '_id' or k == 'password':
                continue
            if hasattr(v, 'binary') or type(v).__name__ == 'ObjectId':
                base[k.lower()] = str(v)
            else:
                base[k.lower()] = v
        return base

    def __getattr__(self, item):
        self.touch()
        if item in self._extra_fields:
            return self._extra_fields[item]
        raise AttributeError(f"'UserDTO' object has no attribute '{item}'")

    def __setattr__(self, key, value):
        if key in {'user_id', 'account_key', 'user_key', 'roles', '_refresh_tokens', '_refresh_token_cache', '_extra_fields', '_last_activity', 'settings', 'subscription', 'password'}:
            super().__setattr__(key, value)
        else:
            self._extra_fields[key] = value
        # Removed self.touch() to prevent recursion

    @classmethod
    def get_from_cache(cls, user_key):
        user = cls._cache.get(user_key)
        if user:
            user.touch()
        return user

    @classmethod
    def cleanup_cache(cls):
        now = int(time.time())
        expired_keys = [k for k, v in cls._cache.items() if now - v._last_activity > cls._CACHE_EXPIRY_SECONDS]
        for k in expired_keys:
            user_obj = cls._cache[k]
            db_user = user_repo.find_one("users", {"user_key": k})
            if db_user:
                db_user.pop('_id', None)
                db_last_update = int(db_user.get('last_update', 0))
                # Only update DB if cache is newer than DB
                if user_obj._last_activity > db_last_update or user_obj.to_dict() != db_user:
                    user_repo.update("users", {"user_key": k}, user_obj.to_dict())
            del cls._cache[k]

    @classmethod
    def cache_size(cls):
        return len(cls._cache)

    @classmethod
    def find_by_user_key(cls, user_key, account_key=None):
        cached = cls.get_from_cache(user_key)
        if cached and (account_key is None or cached.account_key == account_key):
            return cached
        query = {'user_key': user_key}
        if account_key:
            query['account_key'] = account_key
        user_doc = user_repo.find_one("users", query)
        if not user_doc:
            return None
        user_doc.pop('_id', None)
        user_doc = {k.lower(): v for k, v in user_doc.items()}
        return cls(**user_doc)

    @classmethod
    def find_many_by_account(cls, account_key, self_user_key=None):
        users = user_repo.find_many("users", {"account_key": account_key})
        seen_keys = set()
        result = []
        for u in users:
            u.pop('_id', None)
            u = {k.lower(): v for k, v in u.items()}
            user_key = u['user_key']
            if user_key in seen_keys:
                continue  # skip duplicates
            seen_keys.add(user_key)
            cached = cls.get_from_cache(user_key)
            if cached:
                user_dto = cached
            else:
                user_dto = cls(**u)
            # Always include self and all users
            result.append(user_dto.to_dict())
        return result

    def save(self):
        user_repo.update("users", {"user_key": self.user_key}, self.to_dict())

    def save_profile(self, profile_data):
        self.profile = profile_data
        self.save()

    @classmethod
    def create(cls, user_data):
        user_id = user_repo.create("users", user_data)
        return user_id

    def delete(self):
        user_repo.delete("users", {"user_key": self.user_key})
