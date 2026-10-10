"""Service for managing user data connections (MCP integrations)."""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .models.connection import UserDataConnection

logger = logging.getLogger(__name__)

# Provider catalog - built-in, not stored in DB
AVAILABLE_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "google_calendar": {
        "provider_type": "calendar",
        "display_name": "Google 日历",
        "auth_type": "oauth2",
        "default_scopes": ["read_events", "write_events"],
        "icon_url": "/static/icons/google-calendar.png",
        "description": "读取和管理 Google 日历事件",
    },
    "apple_calendar": {
        "provider_type": "calendar",
        "display_name": "Apple 日历",
        "auth_type": "oauth2",
        "default_scopes": ["read_events"],
        "icon_url": "/static/icons/apple-calendar.png",
        "description": "读取 Apple 日历事件",
    },
    "outlook_calendar": {
        "provider_type": "calendar",
        "display_name": "Outlook 日历",
        "auth_type": "oauth2",
        "default_scopes": ["read_events", "write_events"],
        "icon_url": "/static/icons/outlook.png",
        "description": "读取和管理 Outlook 日历事件",
    },
    "gmail": {
        "provider_type": "email",
        "display_name": "Gmail",
        "auth_type": "oauth2",
        "default_scopes": ["read_mail"],
        "icon_url": "/static/icons/gmail.png",
        "description": "读取 Gmail 邮件摘要",
    },
    "outlook_mail": {
        "provider_type": "email",
        "display_name": "Outlook 邮箱",
        "auth_type": "oauth2",
        "default_scopes": ["read_mail"],
        "icon_url": "/static/icons/outlook.png",
        "description": "读取 Outlook 邮件摘要",
    },
    "qq_mail": {
        "provider_type": "email",
        "display_name": "QQ 邮箱",
        "auth_type": "oauth2",
        "default_scopes": ["read_mail"],
        "icon_url": "/static/icons/qq-mail.png",
        "description": "读取 QQ 邮箱摘要",
    },
    "notion": {
        "provider_type": "notes",
        "display_name": "Notion",
        "auth_type": "oauth2",
        "default_scopes": ["read_content", "write_content"],
        "icon_url": "/static/icons/notion.png",
        "description": "读取和写入 Notion 笔记",
    },
    "apple_notes": {
        "provider_type": "notes",
        "display_name": "Apple 备忘录",
        "auth_type": "mcp_direct",
        "default_scopes": ["read_notes"],
        "icon_url": "/static/icons/apple-notes.png",
        "description": "通过本地 MCP 读取备忘录",
    },
    "amap": {
        "provider_type": "transport",
        "display_name": "高德地图",
        "auth_type": "api_key",
        "default_scopes": ["location", "route"],
        "icon_url": "/static/icons/amap.png",
        "description": "位置和路线查询",
    },
    "jd": {
        "provider_type": "shopping",
        "display_name": "京东",
        "auth_type": "oauth2",
        "default_scopes": ["read_orders"],
        "icon_url": "/static/icons/jd.png",
        "description": "查看京东订单历史",
    },
    "mi_home": {
        "provider_type": "smart_home",
        "display_name": "米家",
        "auth_type": "oauth2",
        "default_scopes": ["read_devices", "control_devices"],
        "icon_url": "/static/icons/mi-home.png",
        "description": "智能家居设备控制",
    },
}


def _connection_to_dict(conn: UserDataConnection) -> Dict[str, Any]:
    """Convert a UserDataConnection ORM instance to a response dict."""
    return {
        "id": str(conn.id),
        "user_id": str(conn.user_id),
        "family_id": str(conn.family_id),
        "provider_type": conn.provider_type,
        "provider_name": conn.provider_name,
        "display_name": conn.display_name,
        "icon_url": conn.icon_url,
        "connection_status": conn.connection_status,
        "auth_type": conn.auth_type,
        "scopes": conn.scopes,
        "mcp_server_url": conn.mcp_server_url,
        "mcp_server_config": conn.mcp_server_config,
        "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        "last_error": conn.last_error,
        "sync_frequency_minutes": conn.sync_frequency_minutes,
        "metadata": conn.metadata_,
        "is_active": conn.is_active,
        "created_at": conn.created_at.isoformat() if conn.created_at else None,
        "updated_at": conn.updated_at.isoformat() if conn.updated_at else None,
    }


class ConnectionService:
    """Service for managing user data connections."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def list_connections(
        self, user_id: UUID, family_id: UUID
    ) -> List[Dict[str, Any]]:
        """List all active connections for a user."""
        result = await self.db.execute(
            select(UserDataConnection).where(
                and_(
                    UserDataConnection.user_id == user_id,
                    UserDataConnection.family_id == family_id,
                    UserDataConnection.is_active.is_(True),
                )
            )
        )
        connections = result.scalars().all()
        return [_connection_to_dict(c) for c in connections]

    async def get_available_providers(self) -> List[Dict[str, Any]]:
        """Return the built-in provider catalog, grouped by provider_type."""
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for name, info in AVAILABLE_PROVIDERS.items():
            provider_type = info["provider_type"]
            entry = {
                "provider_name": name,
                "provider_type": provider_type,
                "display_name": info["display_name"],
                "auth_type": info["auth_type"],
                "default_scopes": info["default_scopes"],
                "icon_url": info["icon_url"],
                "description": info["description"],
            }
            grouped.setdefault(provider_type, []).append(entry)

        result = []
        for provider_type, providers in grouped.items():
            result.append({
                "provider_type": provider_type,
                "providers": providers,
            })
        return result

    async def create_connection(
        self,
        user_id: UUID,
        family_id: UUID,
        provider_name: str,
        display_name: Optional[str] = None,
        auth_type: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        mcp_server_url: Optional[str] = None,
        mcp_server_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new connection record.

        If provider_name is in AVAILABLE_PROVIDERS, defaults are filled from the
        catalog. Otherwise it is treated as a custom MCP connection.
        """
        catalog_entry = AVAILABLE_PROVIDERS.get(provider_name)
        if catalog_entry:
            provider_type = catalog_entry["provider_type"]
            resolved_display_name = display_name or catalog_entry["display_name"]
            resolved_auth_type = auth_type or catalog_entry["auth_type"]
            resolved_scopes = scopes if scopes is not None else catalog_entry["default_scopes"]
            icon_url = catalog_entry["icon_url"]
        else:
            provider_type = "custom"
            resolved_display_name = display_name or provider_name
            resolved_auth_type = auth_type or "mcp_direct"
            resolved_scopes = scopes or []
            icon_url = None

        conn = UserDataConnection(
            user_id=user_id,
            family_id=family_id,
            provider_type=provider_type,
            provider_name=provider_name,
            display_name=resolved_display_name,
            icon_url=icon_url,
            auth_type=resolved_auth_type,
            scopes=resolved_scopes,
            connection_status="disconnected",
            mcp_server_url=mcp_server_url,
            mcp_server_config=mcp_server_config,
        )
        self.db.add(conn)
        await self.db.flush()
        return _connection_to_dict(conn)

    async def delete_connection(
        self, connection_id: UUID, user_id: UUID
    ) -> None:
        """Soft-delete a connection (set is_active=False)."""
        result = await self.db.execute(
            select(UserDataConnection).where(
                and_(
                    UserDataConnection.id == connection_id,
                    UserDataConnection.user_id == user_id,
                    UserDataConnection.is_active.is_(True),
                )
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None:
            raise ValueError(f"Connection {connection_id} not found")
        conn.is_active = False
        conn.connection_status = "disconnected"
        await self.db.flush()

    async def update_connection(
        self,
        connection_id: UUID,
        user_id: UUID,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update connection scopes/config."""
        result = await self.db.execute(
            select(UserDataConnection).where(
                and_(
                    UserDataConnection.id == connection_id,
                    UserDataConnection.user_id == user_id,
                    UserDataConnection.is_active.is_(True),
                )
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None:
            raise ValueError(f"Connection {connection_id} not found")

        allowed_fields = {
            "scopes", "sync_frequency_minutes", "mcp_server_url",
            "mcp_server_config", "display_name",
        }
        for key, value in updates.items():
            if key in allowed_fields and hasattr(conn, key):
                setattr(conn, key, value)

        await self.db.flush()
        return _connection_to_dict(conn)

    async def initiate_oauth(
        self,
        provider_name: str,
        user_id: UUID,
        redirect_uri: str,
    ) -> str:
        """Generate OAuth authorization URL for the provider.

        Returns the authorization URL. The actual OAuth flow (token exchange,
        etc.) is handled externally by the provider-specific adapter.
        """
        catalog_entry = AVAILABLE_PROVIDERS.get(provider_name)
        if not catalog_entry:
            raise ValueError(f"Unknown provider: {provider_name}")
        if catalog_entry["auth_type"] != "oauth2":
            raise ValueError(
                f"Provider {provider_name} does not support OAuth2 "
                f"(auth_type={catalog_entry['auth_type']})"
            )

        # Build a state token containing the user reference so the callback
        # can associate the response with the right user.
        import secrets
        state = secrets.token_urlsafe(32)

        # Store state in the connection metadata for later verification.
        # The actual OAuth URLs would be provider-specific; for now we return a
        # placeholder that the front-end / mobile client will handle.
        auth_url = (
            f"https://auth.secretary.app/oauth/{provider_name}"
            f"?redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&user_id={user_id}"
        )
        logger.info(
            "OAuth initiated for provider=%s user=%s", provider_name, user_id
        )
        return auth_url

    async def handle_oauth_callback(
        self,
        provider_name: str,
        user_id: UUID,
        family_id: UUID,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        """Handle OAuth callback, store encrypted credentials, return connection."""
        from ...core.auth.encryption_service import encryption_service

        catalog_entry = AVAILABLE_PROVIDERS.get(provider_name)
        if not catalog_entry:
            raise ValueError(f"Unknown provider: {provider_name}")

        # In production, exchange the code for tokens via the provider's token
        # endpoint. For now, we store the authorization code as the credential
        # placeholder and mark the connection as connected.
        credentials_json = json.dumps({
            "authorization_code": code,
            "state": state,
        })
        encrypted = await encryption_service.encrypt(credentials_json, family_id)

        # Upsert: reactivate if soft-deleted, or create new
        result = await self.db.execute(
            select(UserDataConnection).where(
                and_(
                    UserDataConnection.user_id == user_id,
                    UserDataConnection.provider_name == provider_name,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.encrypted_credentials = encrypted.encode()
            existing.connection_status = "connected"
            existing.is_active = True
            existing.scopes = catalog_entry["default_scopes"]
            existing.last_error = None
            existing.family_id = family_id
            await self.db.flush()
            return _connection_to_dict(existing)

        conn = UserDataConnection(
            user_id=user_id,
            family_id=family_id,
            provider_type=catalog_entry["provider_type"],
            provider_name=provider_name,
            display_name=catalog_entry["display_name"],
            icon_url=catalog_entry["icon_url"],
            auth_type="oauth2",
            scopes=catalog_entry["default_scopes"],
            encrypted_credentials=encrypted.encode(),
            connection_status="connected",
        )
        self.db.add(conn)
        await self.db.flush()
        return _connection_to_dict(conn)
