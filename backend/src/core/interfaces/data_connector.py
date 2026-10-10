"""
IDataConnector interface - Core abstraction for external data source connectors.

This interface defines the contract that all data source connectors must implement.
It supports multiple authorization methods (OAuth 2.0, OAuth 1.0a, API Key, MCP, etc.)
and provides a standardized way to sync data from external services.

Example connectors:
- Google Calendar
- Gmail
- Outlook Calendar/Mail
- iCloud Calendar
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, AsyncGenerator
from uuid import UUID

from pydantic import BaseModel, Field
from ..utils.timezone import utc_now


class DataConnectorError(Exception):
    """Base exception for data connector errors."""
    pass


class AuthorizationError(DataConnectorError):
    """Raised when authorization fails."""
    pass


class TokenExpiredError(DataConnectorError):
    """Raised when the access token has expired."""
    pass


class SyncError(DataConnectorError):
    """Raised when data synchronization fails."""
    pass


class RateLimitError(DataConnectorError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthType(str, Enum):
    """Supported authorization types."""
    OAUTH2 = "oauth2"
    OAUTH1 = "oauth1"
    API_KEY = "api_key"
    MCP = "mcp"
    BASIC = "basic"
    IMAP = "imap"
    CUSTOM = "custom"


class ConnectionStatus(str, Enum):
    """Connection status enum."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"
    EXPIRED = "expired"  # Token expired, needs refresh or reauth


class SyncFrequency(str, Enum):
    """Data synchronization frequency."""
    REALTIME = "realtime"  # Via webhook push
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"


class DataCategory(str, Enum):
    """Data source categories."""
    CALENDAR = "calendar"
    EMAIL = "email"
    ECOMMERCE = "ecommerce"
    FOOD_DELIVERY = "food_delivery"
    SOCIAL = "social"
    FINANCE = "finance"
    HEALTH = "health"
    LOCATION = "location"
    TRAVEL = "travel"
    PRODUCTIVITY = "productivity"
    OTHER = "other"


class ConnectorCapability(BaseModel):
    """Describes what a connector can do."""
    can_read: bool = True
    can_write: bool = False
    supports_webhook: bool = False
    supports_incremental_sync: bool = True
    supports_full_sync: bool = True
    rate_limit_per_hour: Optional[int] = None
    max_historical_days: Optional[int] = 90  # How far back can we sync


class ConnectorMetadata(BaseModel):
    """Connector metadata for discovery and display."""
    id: str  # Unique identifier, e.g., "google_calendar"
    name: str  # Internal name
    display_name: str  # Localized display name
    display_name_zh: str  # Chinese display name
    description: str  # English description
    description_zh: str  # Chinese description
    icon: str  # Icon identifier for frontend
    category: DataCategory
    auth_type: AuthType
    capabilities: ConnectorCapability = Field(default_factory=ConnectorCapability)
    required_scopes: List[str] = Field(default_factory=list)
    optional_scopes: List[str] = Field(default_factory=list)
    data_retention_days: int = 90  # How long to keep synced data
    is_available: bool = True  # Whether this connector is currently usable
    regions: List[str] = Field(default_factory=lambda: ["CN", "GLOBAL"])
    # Privacy and compliance
    privacy_policy_url: Optional[str] = None
    data_usage_description: str = ""
    data_usage_description_zh: str = ""


class ConnectionCredentials(BaseModel):
    """Encrypted credentials for a connection."""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    api_key: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_type: str = "Bearer"
    scope: Optional[str] = None
    extra_data: Dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        if self.expires_at is None:
            return False
        return utc_now() > self.expires_at


class SyncResult(BaseModel):
    """Result of a sync operation."""
    success: bool
    records_synced: int = 0
    records_updated: int = 0
    records_deleted: int = 0
    records_failed: int = 0
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    last_sync_cursor: Optional[str] = None
    next_sync_at: Optional[datetime] = None
    warnings: List[str] = Field(default_factory=list)


@dataclass
class DataRecord:
    """
    A single record synced from an external source.

    This is the standardized format that all connectors must produce.
    """
    id: str  # Unique ID for this record
    source_id: str  # External system's ID for this record
    data_type: str  # e.g., "calendar_event", "email", "order"
    content: Dict[str, Any]  # The actual data
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Optional normalized fields for common data types
    title: Optional[str] = None
    preview: Optional[str] = None  # Short preview text
    extracted_entities: Dict[str, Any] = field(default_factory=dict)


class IDataConnector(ABC):
    """
    Interface for external data source connectors.

    All connectors must implement this interface to be registered with
    the DataConnectionManager.
    """

    @property
    @abstractmethod
    def metadata(self) -> ConnectorMetadata:
        """
        Get connector metadata.

        Returns:
            ConnectorMetadata describing this connector's capabilities.
        """
        pass

    @abstractmethod
    async def get_auth_url(
        self,
        user_id: UUID,
        family_id: UUID,
        redirect_uri: str,
        scopes: Optional[List[str]] = None,
        state: Optional[str] = None
    ) -> str:
        """
        Generate the OAuth authorization URL.

        For non-OAuth connectors, this may return a configuration page URL
        or raise NotImplementedError.

        Args:
            user_id: The user initiating the connection.
            family_id: The user's family ID.
            redirect_uri: Where to redirect after authorization.
            scopes: Override default scopes (optional).
            state: State parameter for CSRF protection (usually connection_id).

        Returns:
            URL to redirect the user to for authorization.

        Raises:
            DataConnectorError: If URL generation fails.
        """
        pass

    @abstractmethod
    async def handle_callback(
        self,
        user_id: UUID,
        family_id: UUID,
        code: str,
        state: Optional[str] = None
    ) -> ConnectionCredentials:
        """
        Handle the OAuth callback and exchange code for tokens.

        Args:
            user_id: The user completing authorization.
            family_id: The user's family ID.
            code: The authorization code from the callback.
            state: The state parameter for verification.

        Returns:
            ConnectionCredentials containing access and refresh tokens.

        Raises:
            AuthorizationError: If token exchange fails.
        """
        pass

    @abstractmethod
    async def refresh_credentials(
        self,
        credentials: ConnectionCredentials
    ) -> ConnectionCredentials:
        """
        Refresh expired credentials.

        Args:
            credentials: Current credentials with refresh token.

        Returns:
            New ConnectionCredentials with fresh access token.

        Raises:
            AuthorizationError: If refresh fails (user must reauthorize).
        """
        pass

    @abstractmethod
    async def test_connection(
        self,
        credentials: ConnectionCredentials
    ) -> bool:
        """
        Test if the connection is working.

        Args:
            credentials: The credentials to test.

        Returns:
            True if connection is valid, False otherwise.
        """
        pass

    @abstractmethod
    async def sync_data(
        self,
        user_id: UUID,
        family_id: UUID,
        credentials: ConnectionCredentials,
        since: Optional[datetime] = None,
        cursor: Optional[str] = None,
        full_sync: bool = False
    ) -> AsyncGenerator[DataRecord, None]:
        """
        Synchronize data from the external source.

        This is an async generator that yields DataRecord objects.
        It supports both incremental sync (using since/cursor) and
        full sync.

        Args:
            user_id: The user to sync for.
            family_id: The user's family ID.
            credentials: Valid credentials for the connection.
            since: Only sync data modified after this time.
            cursor: Pagination cursor from previous sync.
            full_sync: If True, ignore since/cursor and do full sync.

        Yields:
            DataRecord objects representing synced data.

        Raises:
            TokenExpiredError: If credentials are expired.
            SyncError: If synchronization fails.
            RateLimitError: If rate limit is exceeded.
        """
        pass

    @abstractmethod
    async def disconnect(
        self,
        credentials: ConnectionCredentials
    ) -> bool:
        """
        Disconnect and revoke authorization.

        This should revoke the token on the external service's side
        when possible.

        Args:
            credentials: The credentials to revoke.

        Returns:
            True if successfully disconnected.
        """
        pass

    # Optional methods - connectors can override these

    async def setup_webhook(
        self,
        user_id: UUID,
        family_id: UUID,
        credentials: ConnectionCredentials,
        webhook_url: str
    ) -> Optional[str]:
        """
        Set up a webhook for real-time updates.

        Args:
            user_id: The user to set up webhook for.
            family_id: The user's family ID.
            credentials: Valid credentials.
            webhook_url: URL to receive webhook events.

        Returns:
            Webhook ID if successfully set up, None if not supported.
        """
        return None

    async def handle_webhook(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> List[DataRecord]:
        """
        Handle incoming webhook payload.

        Args:
            payload: The webhook payload.
            headers: HTTP headers for signature verification.

        Returns:
            List of DataRecord objects from the webhook.
        """
        return []

    async def remove_webhook(
        self,
        credentials: ConnectionCredentials,
        webhook_id: str
    ) -> bool:
        """
        Remove a previously registered webhook.

        Args:
            credentials: Valid credentials.
            webhook_id: The webhook ID to remove.

        Returns:
            True if successfully removed.
        """
        return True

    def get_default_sync_frequency(self) -> SyncFrequency:
        """Get the recommended sync frequency for this connector."""
        if self.metadata.capabilities.supports_webhook:
            return SyncFrequency.REALTIME
        return SyncFrequency.DAILY

    def normalize_record(self, raw_data: Dict[str, Any], data_type: str) -> DataRecord:
        """
        Normalize raw data into a DataRecord.

        Subclasses can override this to provide custom normalization.

        Args:
            raw_data: Raw data from the external API.
            data_type: The type of data being normalized.

        Returns:
            Normalized DataRecord.
        """
        return DataRecord(
            id=str(raw_data.get("id", "")),
            source_id=str(raw_data.get("id", "")),
            data_type=data_type,
            content=raw_data,
            created_at=utc_now(),
            updated_at=utc_now(),
        )


# Connector registry for plugin-like registration
_connector_registry: Dict[str, type] = {}


def register_connector(connector_class_or_name=None):
    """
    Decorator to register a connector class.

    Usage:
        @register_connector
        class GoogleCalendarConnector(IDataConnector):
            ...

        # Or with an optional name argument (name is ignored, uses metadata.id):
        @register_connector("google_calendar")
        class GoogleCalendarConnector(IDataConnector):
            ...
    """
    def _register(cls: type) -> type:
        instance = cls()
        _connector_registry[instance.metadata.id] = cls
        return cls

    # Called as @register_connector (without parentheses)
    if isinstance(connector_class_or_name, type):
        return _register(connector_class_or_name)

    # Called as @register_connector() or @register_connector("name")
    return _register


def get_registered_connectors() -> Dict[str, type]:
    """Get all registered connector classes."""
    return _connector_registry.copy()


def get_connector_class(connector_id: str) -> Optional[type]:
    """Get a connector class by ID."""
    return _connector_registry.get(connector_id)
