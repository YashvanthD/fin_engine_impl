"""Application configuration settings.

This module centralizes all configuration values loaded from:
1. config.base.yaml (shared defaults)
2. config.{env}.yaml (environment-specific: dev, staging, prod)
3. config.local.yaml (local overrides, git-ignored)
4. Environment variables (highest priority)

Default environment is 'development' (DEV).

Usage:
    from config.settings import config

    # Access config values
    secret = config.JWT_SECRET
    debug = config.DEBUG

    # Check current environment
    env = config.ENV  # 'development', 'staging', or 'production'
"""
import os
from pathlib import Path
from typing import Optional, Any, Dict
import yaml


# Environment name mappings
ENV_ALIASES = {
    'dev': 'development',
    'development': 'development',
    'staging': 'staging',
    'stage': 'staging',
    'prod': 'production',
    'production': 'production',
}

# Default environment
DEFAULT_ENV = 'development'


class Config:
    """Centralized application configuration.

    Loads configuration from YAML files based on environment.

    Priority (highest to lowest):
    1. Environment variables
    2. config.local.yaml (for local development overrides)
    3. config.{env}.yaml (environment-specific: dev, staging, prod)
    4. config.base.yaml (shared defaults)

    Environment is determined by:
    1. FLASK_ENV environment variable
    2. APP_ENV environment variable
    3. Default: 'development'
    """

    _config_data: Dict[str, Any] = {}
    _loaded: bool = False
    _current_env: str = DEFAULT_ENV

    def __init__(self):
        if not Config._loaded:
            self._load_config()

    @classmethod
    def _get_environment(cls) -> str:
        """Determine current environment from env vars or default to dev."""
        env = os.getenv('FLASK_ENV') or os.getenv('APP_ENV') or DEFAULT_ENV
        env = env.lower().strip()
        return ENV_ALIASES.get(env, DEFAULT_ENV)

    def _load_config(self):
        """Load configuration from YAML files based on environment."""
        config_dir = Path(__file__).parent
        Config._current_env = self._get_environment()

        # Start with empty config
        Config._config_data = {}

        # 1. Load base config (shared defaults)
        base_config_path = config_dir / 'config.base.yaml'
        if base_config_path.exists():
            with open(base_config_path, 'r') as f:
                Config._config_data = yaml.safe_load(f) or {}

        # 2. Load environment-specific config
        env_config_map = {
            'development': 'config.dev.yaml',
            'staging': 'config.staging.yaml',
            'production': 'config.prod.yaml',
        }
        env_config_file = env_config_map.get(Config._current_env, 'config.dev.yaml')
        env_config_path = config_dir / env_config_file

        if env_config_path.exists():
            with open(env_config_path, 'r') as f:
                env_data = yaml.safe_load(f) or {}
                Config._config_data = self._deep_merge(Config._config_data, env_data)

        # 3. Load local overrides (not in git)
        local_config_path = config_dir / 'config.local.yaml'
        if local_config_path.exists():
            with open(local_config_path, 'r') as f:
                local_data = yaml.safe_load(f) or {}
                Config._config_data = self._deep_merge(Config._config_data, local_data)

        Config._loaded = True

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _get_yaml_value(self, *keys, default=None) -> Any:
        """Get a nested value from YAML config."""
        value = Config._config_data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    @classmethod
    def reload(cls):
        """Reload configuration (useful for testing)."""
        cls._loaded = False
        cls._config_data = {}
        instance = cls()
        return instance

    # ==========================================================================
    # Environment Info
    # ==========================================================================

    @property
    def CURRENT_ENV(self) -> str:
        """Current environment name."""
        return Config._current_env

    @property
    def IS_DEV(self) -> bool:
        """Check if running in development environment."""
        return Config._current_env == 'development'

    @property
    def IS_STAGING(self) -> bool:
        """Check if running in staging environment."""
        return Config._current_env == 'staging'

    @property
    def IS_PROD(self) -> bool:
        """Check if running in production environment."""
        return Config._current_env == 'production'

    # ==========================================================================
    # Application Settings
    # ==========================================================================

    @property
    def DEBUG(self) -> bool:
        """Flask debug mode."""
        env_val = os.getenv('FLASK_DEBUG', '').lower()
        if env_val:
            return env_val in ('1', 'true', 'yes')
        return self._get_yaml_value('app', 'debug', default=False)

    @property
    def ENV(self) -> str:
        """Application environment (development, staging, production)."""
        return Config._current_env

    @property
    def PORT(self) -> int:
        """Server port."""
        env_val = os.getenv('PORT')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('app', 'port', default=5000)

    @property
    def APP_NAME(self) -> str:
        """Application name."""
        return os.getenv('APP_NAME') or self._get_yaml_value('app', 'name', default='Fin Engine API')

    @property
    def APP_VERSION(self) -> str:
        """Application version."""
        return self._get_yaml_value('app', 'version', default='1.0.0')

    # ==========================================================================
    # Security Settings
    # ==========================================================================

    @property
    def MASTER_ADMIN_PASSWORD(self) -> Optional[str]:
        """Master admin password for company/admin registration."""
        env_val = os.getenv('MASTER_ADMIN_PASSWORD')
        if env_val:
            return env_val
        yaml_val = self._get_yaml_value('security', 'master_admin_password')
        if yaml_val:
            return yaml_val
        # Fallback for dev mode only
        if self.IS_DEV:
            return 'password'
        return None

    @property
    def JWT_SECRET(self) -> Optional[str]:
        """JWT secret key for token signing. Required in production."""
        return os.getenv('JWT_SECRET') or self._get_yaml_value('security', 'jwt', 'secret')

    @property
    def JWT_ALGORITHM(self) -> str:
        """JWT algorithm (default: HS256)."""
        return os.getenv('JWT_ALGORITHM') or self._get_yaml_value('security', 'jwt', 'algorithm', default='HS256')

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        """Access token expiry in minutes."""
        env_val = os.getenv('ACCESS_TOKEN_MINUTES')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('security', 'jwt', 'access_token_expire_minutes', default=10080)

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        """Refresh token expiry in days."""
        env_val = os.getenv('REFRESH_TOKEN_DAYS')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('security', 'jwt', 'refresh_token_expire_days', default=90)

    @property
    def BCRYPT_ROUNDS(self) -> int:
        """Bcrypt hashing rounds."""
        env_val = os.getenv('BCRYPT_ROUNDS')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('security', 'bcrypt_rounds', default=12)

    # ==========================================================================
    # Database Settings
    # ==========================================================================

    @property
    def MONGO_URI(self) -> str:
        """MongoDB connection URI."""
        return os.getenv('MONGO_URI') or self._get_yaml_value('database', 'mongo_uri', default='mongodb://localhost:27017')

    @property
    def USER_DB_NAME(self) -> str:
        """User database name."""
        return os.getenv('USER_DB_NAME') or self._get_yaml_value('database', 'databases', 'user', default='user_db')

    @property
    def MEDIA_DB_NAME(self) -> str:
        """Media database name."""
        return os.getenv('MEDIA_DB_NAME') or self._get_yaml_value('database', 'databases', 'media', default='media_db')

    @property
    def EXPENSES_DB_NAME(self) -> str:
        """Expenses database name."""
        return os.getenv('EXPENSES_DB_NAME') or self._get_yaml_value('database', 'databases', 'expenses', default='expenses_db')

    @property
    def FISH_DB_NAME(self) -> str:
        """Fish database name."""
        return os.getenv('FISH_DB_NAME') or self._get_yaml_value('database', 'databases', 'fish', default='fish_db')

    @property
    def ANALYTICS_DB_NAME(self) -> str:
        """Analytics database name."""
        return os.getenv('ANALYTICS_DB_NAME') or self._get_yaml_value('database', 'databases', 'analytics', default='analytics_db')

    # ==========================================================================
    # CORS Settings
    # ==========================================================================

    @property
    def CORS_ORIGINS(self) -> str:
        """Allowed CORS origins."""
        return os.getenv('CORS_ORIGINS') or self._get_yaml_value('cors', 'origins', default='*')

    @property
    def CORS_ORIGINS_LIST(self) -> list:
        """Get CORS origins as a list."""
        origins = self.CORS_ORIGINS
        if origins == '*':
            return ['*']
        return [o.strip() for o in origins.split(',') if o.strip()]

    # ==========================================================================
    # Timezone Settings
    # ==========================================================================

    @property
    def DEFAULT_TIMEZONE(self) -> str:
        """Default timezone for date/time operations."""
        return os.getenv('DEFAULT_TIMEZONE') or self._get_yaml_value('timezone', 'default', default='Asia/Kolkata')

    # ==========================================================================
    # Logging Settings
    # ==========================================================================

    @property
    def LOG_LEVEL(self) -> str:
        """Logging level."""
        env_val = os.getenv('LOG_LEVEL')
        if env_val:
            return env_val.upper()
        # If debug mode, use DEBUG level
        if self.LOG_DEBUG:
            return 'DEBUG'
        return self._get_yaml_value('logging', 'level', default='INFO')

    @property
    def LOG_DEBUG(self) -> bool:
        """Enable debug logging (verbose)."""
        env_val = os.getenv('LOG_DEBUG', '').lower()
        if env_val:
            return env_val in ('1', 'true', 'yes')
        return self._get_yaml_value('logging', 'debug', default=False)

    @property
    def LOG_PATTERN(self) -> str:
        """Log format pattern."""
        env_val = os.getenv('LOG_PATTERN')
        if env_val:
            return env_val
        return self._get_yaml_value('logging', 'pattern', default='%(message)s')

    @property
    def LOG_INCLUDE_DATETIME(self) -> bool:
        """Include datetime in logs."""
        env_val = os.getenv('LOG_INCLUDE_DATETIME', '').lower()
        if env_val:
            return env_val in ('1', 'true', 'yes')
        return self._get_yaml_value('logging', 'include_datetime', default=False)

    @property
    def LOG_INCLUDE_NAME(self) -> bool:
        """Include logger name in logs."""
        env_val = os.getenv('LOG_INCLUDE_NAME', '').lower()
        if env_val:
            return env_val in ('1', 'true', 'yes')
        return self._get_yaml_value('logging', 'include_name', default=False)

    @property
    def LOG_INCLUDE_LEVEL(self) -> bool:
        """Include log level in logs."""
        env_val = os.getenv('LOG_INCLUDE_LEVEL', '').lower()
        if env_val:
            return env_val in ('1', 'true', 'yes')
        return self._get_yaml_value('logging', 'include_level', default=True)

    @property
    def LOG_DATE_FORMAT(self) -> str:
        """Date format for logs."""
        return self._get_yaml_value('logging', 'date_format', default='%H:%M:%S')

    @property
    def LOG_FORMAT(self) -> str:
        """Build log format string based on config options."""
        # If custom pattern is set, use it
        pattern = self.LOG_PATTERN
        if pattern and pattern != '%(message)s':
            return pattern

        # Build format dynamically
        parts = []
        if self.LOG_INCLUDE_DATETIME:
            parts.append('%(asctime)s')
        if self.LOG_INCLUDE_NAME:
            parts.append('%(name)s')
        if self.LOG_INCLUDE_LEVEL:
            parts.append('%(levelname)s')
        parts.append('%(message)s')

        return ' - '.join(parts) if len(parts) > 1 else parts[0]

    # ==========================================================================
    # Notification Settings
    # ==========================================================================

    @property
    def SCHEDULER_INTERVAL_SECONDS(self) -> int:
        """Task scheduler interval in seconds."""
        env_val = os.getenv('SCHEDULER_INTERVAL_SECONDS')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('notification', 'scheduler_interval_seconds', default=60)

    @property
    def NOTIFICATION_WORKER_ENABLED(self) -> bool:
        """Whether notification worker is enabled."""
        env_val = os.getenv('NOTIFICATION_WORKER_ENABLED', '').lower()
        if env_val:
            return env_val in ('1', 'true', 'yes')
        return self._get_yaml_value('notification', 'worker_enabled', default=True)

    # ==========================================================================
    # OpenAI / AI Settings
    # ==========================================================================

    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        """OpenAI API key."""
        return os.getenv('OPENAI_API_KEY') or self._get_yaml_value('openai', 'api_key')

    @property
    def OPENAI_MODEL(self) -> str:
        """Default OpenAI model."""
        return os.getenv('OPENAI_MODEL') or self._get_yaml_value('openai', 'model', default='gpt-4o-mini')

    @property
    def OPENAI_MAX_TOKENS(self) -> int:
        """Max tokens for OpenAI responses."""
        env_val = os.getenv('OPENAI_MAX_TOKENS')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('openai', 'max_tokens', default=2000)

    @property
    def OPENAI_TEMPERATURE(self) -> float:
        """Default temperature for OpenAI."""
        env_val = os.getenv('OPENAI_TEMPERATURE')
        if env_val:
            return float(env_val)
        return self._get_yaml_value('openai', 'temperature', default=0.7)

    @property
    def OPENAI_TIMEOUT(self) -> int:
        """OpenAI request timeout in seconds."""
        env_val = os.getenv('OPENAI_TIMEOUT')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('openai', 'timeout', default=30)

    # ==========================================================================
    # Feature Flags
    # ==========================================================================

    @property
    def ENABLE_SWAGGER(self) -> bool:
        """Whether Swagger/OpenAPI docs are enabled."""
        return self._get_yaml_value('features', 'enable_swagger', default=self.IS_DEV)

    @property
    def ENABLE_DEBUG_ENDPOINTS(self) -> bool:
        """Whether debug endpoints are enabled."""
        return self._get_yaml_value('features', 'enable_debug_endpoints', default=self.IS_DEV)

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================

    @property
    def RATE_LIMIT_ENABLED(self) -> bool:
        """Whether rate limiting is enabled."""
        return self._get_yaml_value('rate_limit', 'enabled', default=False)

    @property
    def RATE_LIMIT_PER_MINUTE(self) -> int:
        """Requests per minute limit."""
        return self._get_yaml_value('rate_limit', 'requests_per_minute', default=60)

    # ==========================================================================
    # Upload Settings
    # ==========================================================================

    @property
    def MAX_UPLOAD_SIZE_MB(self) -> int:
        """Maximum file upload size in MB."""
        return self._get_yaml_value('upload', 'max_file_size_mb', default=10)

    @property
    def ALLOWED_UPLOAD_EXTENSIONS(self) -> list:
        """Allowed file upload extensions."""
        return self._get_yaml_value('upload', 'allowed_extensions', default=['jpg', 'jpeg', 'png', 'pdf'])

    # ==========================================================================
    # MCP (Model Context Protocol) Settings
    # ==========================================================================

    @property
    def MCP_ENABLED(self) -> bool:
        """Whether MCP server is enabled."""
        env_val = os.getenv('MCP_ENABLED', '').lower()
        if env_val:
            return env_val in ('1', 'true', 'yes')
        return self._get_yaml_value('mcp', 'enabled', default=False)

    @property
    def MCP_HOST(self) -> str:
        """MCP server host."""
        return os.getenv('MCP_HOST') or self._get_yaml_value('mcp', 'host', default='127.0.0.1')

    @property
    def MCP_PORT(self) -> int:
        """MCP server port."""
        env_val = os.getenv('MCP_PORT')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('mcp', 'port', default=8085)

    @property
    def MCP_TRANSPORT(self) -> str:
        """MCP transport type (stdio, sse, websocket)."""
        return os.getenv('MCP_TRANSPORT') or self._get_yaml_value('mcp', 'transport', default='stdio')

    @property
    def MCP_TOOLS_ENABLED(self) -> bool:
        """Whether MCP tools are enabled."""
        env_val = os.getenv('MCP_TOOLS_ENABLED', '').lower()
        if env_val:
            return env_val in ('1', 'true', 'yes')
        return self._get_yaml_value('mcp', 'tools_enabled', default=True)

    @property
    def MCP_MAX_CONNECTIONS(self) -> int:
        """Maximum MCP connections."""
        env_val = os.getenv('MCP_MAX_CONNECTIONS')
        if env_val:
            return int(env_val)
        return self._get_yaml_value('mcp', 'max_connections', default=10)

    # ==========================================================================
    # Validation Methods
    # ==========================================================================

    def validate_required(self) -> None:
        """Validate that required configuration values are set.

        Raises RuntimeError if required values are missing in production.
        """
        errors = []

        if self.IS_PROD:
            if not self.JWT_SECRET:
                errors.append('JWT_SECRET environment variable is required in production')
            if not self.MASTER_ADMIN_PASSWORD:
                errors.append('MASTER_ADMIN_PASSWORD environment variable is required in production')
            if not self.MONGO_URI or self.MONGO_URI == 'mongodb://localhost:27017':
                errors.append('MONGO_URI should be set to production database in production')
            if self.CORS_ORIGINS == '*':
                errors.append('CORS_ORIGINS should not be "*" in production')

        if errors:
            raise RuntimeError('Configuration errors:\n' + '\n'.join(f'  - {e}' for e in errors))

    def validate_master_password(self, provided_password: Optional[str]) -> tuple:
        """Validate master password for admin operations."""
        import hmac

        master_pwd = self.MASTER_ADMIN_PASSWORD

        if not master_pwd:
            return False, 'Server not configured for admin registration'

        if not provided_password:
            return False, 'Master password is required'

        if not hmac.compare_digest(str(provided_password), str(master_pwd)):
            return False, 'Invalid master password'

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        """Export current configuration as dictionary (for debugging)."""
        return {
            'environment': {
                'current': self.CURRENT_ENV,
                'is_dev': self.IS_DEV,
                'is_staging': self.IS_STAGING,
                'is_prod': self.IS_PROD,
            },
            'app': {
                'debug': self.DEBUG,
                'port': self.PORT,
                'name': self.APP_NAME,
                'version': self.APP_VERSION,
            },
            'security': {
                'jwt_algorithm': self.JWT_ALGORITHM,
                'access_token_exPIRE_MINUTES': self.ACCESS_TOKEN_EXPIRE_MINUTES,
                'refresh_token_expire_days': self.REFRESH_TOKEN_EXPIRE_DAYS,
                'bcrypt_rounds': self.BCRYPT_ROUNDS,
                'jwt_secret_set': bool(self.JWT_SECRET),
                'master_password_set': bool(self.MASTER_ADMIN_PASSWORD),
            },
            'database': {
                'mongo_uri': '***' if self.MONGO_URI else None,
                'user_db': self.USER_DB_NAME,
                'media_db': self.MEDIA_DB_NAME,
                'expenses_db': self.EXPENSES_DB_NAME,
                'fish_db': self.FISH_DB_NAME,
                'analytics_db': self.ANALYTICS_DB_NAME,
            },
            'cors': {
                'origins': self.CORS_ORIGINS,
            },
            'timezone': {
                'default': self.DEFAULT_TIMEZONE,
            },
            'logging': {
                'level': self.LOG_LEVEL,
            },
            'features': {
                'swagger': self.ENABLE_SWAGGER,
                'debug_endpoints': self.ENABLE_DEBUG_ENDPOINTS,
            },
            'mcp': {
                'enabled': self.MCP_ENABLED,
                'host': self.MCP_HOST,
                'port': self.MCP_PORT,
                'transport': self.MCP_TRANSPORT,
                'tools_enabled': self.MCP_TOOLS_ENABLED,
                'max_connections': self.MCP_MAX_CONNECTIONS,
            },
        }


# Singleton config instance
config = Config()


# =============================================================================
# Convenience exports
# =============================================================================

def get_debug() -> bool:
    return config.DEBUG

def get_mongo_uri() -> str:
    return config.MONGO_URI

def get_jwt_secret() -> Optional[str]:
    return config.JWT_SECRET

def get_master_admin_password() -> Optional[str]:
    return config.MASTER_ADMIN_PASSWORD

def get_env() -> str:
    return config.ENV

def is_dev() -> bool:
    return config.IS_DEV

def is_prod() -> bool:
    return config.IS_PROD
