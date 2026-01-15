import time

from fin_server.repository.mongo_helper import get_collection

user_repo = get_collection('users')

class UserDTO:
    # Class-level cache: user_key -> UserDTO
    _cache = {}
    _CACHE_EXPIRY_SECONDS = 86400  # 1 day

    def __init__(self, user_id=None, account_key=None, user_key=None, role=None, authorities=None, refresh_tokens=None, settings=None, subscription=None, password=None, **kwargs):
        # Allow user_id to be optional for backward/DB compatibility; other fields default to None
        self.user_id = user_id
        self.account_key = account_key
        self.user_key = user_key

        # account_key and user_key may be provided via kwargs if not passed directly
        if self.account_key is None and 'account_key' in kwargs:
            self.account_key = kwargs.get('account_key')
        if self.user_key is None and 'user_key' in kwargs:
            self.user_key = kwargs.get('user_key')

        # Role is a single string
        self.role = role or 'user'

        # Authorities are special permissions beyond the role
        self.authorities = authorities if isinstance(authorities, list) else []
        self._refresh_tokens = refresh_tokens or []
        self._refresh_token_cache = set(self._refresh_tokens)
        self.settings = settings or {}
        self.subscription = subscription or {}
        self.password = password
        self._extra_fields = kwargs
        # store last_activity as epoch seconds; UI can convert to IST when displaying
        self._last_activity = int(time.time())
        # Add to cache
        UserDTO._cache[self.user_key] = self

        # Add timezone to settings if not present
        if 'timezone' not in self.settings:
            self.settings['timezone'] = 'Asia/Kolkata'  # Default to IST

    def touch(self):
        # update last_activity to current epoch seconds
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
            'role': self.role,
            'authorities': self.authorities,
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
        if key in {'user_id', 'account_key', 'user_key', 'role', 'authorities', '_refresh_tokens', '_refresh_token_cache', '_extra_fields', '_last_activity', 'settings', 'subscription', 'password'}:
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
        now = int(time.time())  # epoch seconds, UI converts to IST
        expired_keys = [k for k, v in cls._cache.items() if now - v._last_activity > cls._CACHE_EXPIRY_SECONDS]
        for k in expired_keys:
            user_obj = cls._cache[k]
            # Correct repository calls: repository methods expect query/update without collection name
            db_user = user_repo.find_one({"user_key": k})
            if db_user:
                db_user.pop('_id', None)
                db_last_update = int(db_user.get('last_update', 0))
                # Only update DB if cache is newer than DB
                if user_obj._last_activity > db_last_update or user_obj.to_dict() != db_user:
                    user_repo.update({"user_key": k}, user_obj.to_dict())
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
        user_doc = user_repo.find_one(query)
        if not user_doc:
            return None
        # If Mongo returned an ObjectId in '_id', expose it as 'user_id' expected by the DTO
        if '_id' in user_doc:
            user_doc['user_id'] = user_doc['_id']
        user_doc.pop('_id', None)
        user_doc = {k.lower(): v for k, v in user_doc.items()}
        return cls(**user_doc)

    @classmethod
    def find_many_by_account(cls, account_key, self_user_key=None):
        users = user_repo.find_many({"account_key": account_key})
        seen_keys = set()
        result = []
        for u in users:
            # Map MongoDB _id to user_id to satisfy DTO constructor
            if '_id' in u:
                u['user_id'] = u['_id']
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
        # Persist user DTO to DB using repository API (query, update_fields)
        user_repo.update({"user_key": self.user_key}, self.to_dict())

    def save_profile(self, profile_data):
        self.profile = profile_data
        self.save()

    @classmethod
    def create(cls, user_data):
        # Repository.create expects a single data dict
        user_id = user_repo.create(user_data)
        return user_id

    def delete(self):
        user_repo.delete({"user_key": self.user_key})
