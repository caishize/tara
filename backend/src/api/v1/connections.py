"""
Data-connection management API endpoints.

Allows users to link/unlink external data sources (calendar, email,
smart-home, etc.) via OAuth or direct MCP connection.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List, Optional
from uuid import UUID

from ...db.session import get_db
from ...core.auth import get_current_user, get_current_family
from ...modules.member.connection_service import ConnectionService

router = APIRouter(prefix="/connections", tags=["Connections"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ProviderInfo(BaseModel):
    provider_name: str
    provider_type: str
    display_name: str
    auth_type: str
    default_scopes: List[str]
    icon_url: Optional[str] = None
    description: str


class ProviderGroup(BaseModel):
    provider_type: str
    providers: List[ProviderInfo]


class ConnectionResponse(BaseModel):
    id: str
    user_id: str
    family_id: str
    provider_type: str
    provider_name: str
    display_name: str
    icon_url: Optional[str] = None
    connection_status: str
    auth_type: str
    scopes: List[str] = Field(default_factory=list)
    mcp_server_url: Optional[str] = None
    mcp_server_config: Optional[Dict[str, Any]] = None
    last_sync_at: Optional[str] = None
    last_error: Optional[str] = None
    sync_frequency_minutes: int = 60
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OAuthAuthorizeRequest(BaseModel):
    redirect_uri: str


class OAuthAuthorizeResponse(BaseModel):
    authorization_url: str


class UpdateConnectionRequest(BaseModel):
    scopes: Optional[List[str]] = None
    sync_frequency_minutes: Optional[int] = None
    mcp_server_url: Optional[str] = None
    mcp_server_config: Optional[Dict[str, Any]] = None
    display_name: Optional[str] = None


class CreateCustomConnectionRequest(BaseModel):
    provider_name: str
    display_name: Optional[str] = None
    auth_type: Optional[str] = None
    scopes: Optional[List[str]] = None
    mcp_server_url: Optional[str] = None
    mcp_server_config: Optional[Dict[str, Any]] = None


class SyncResponse(BaseModel):
    message: str
    connection_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[ConnectionResponse], include_in_schema=False)
@router.get("/", response_model=List[ConnectionResponse])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """List all active data connections for the current user."""
    service = ConnectionService(db)
    return await service.list_connections(user_id, family_id)


@router.get("/available", response_model=List[ProviderGroup])
async def get_available_providers(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Return the built-in provider catalog grouped by type."""
    service = ConnectionService(db)
    return await service.get_available_providers()


@router.post(
    "/{provider}/authorize",
    response_model=OAuthAuthorizeResponse,
)
async def initiate_oauth(
    provider: str,
    request: OAuthAuthorizeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Start OAuth flow for a provider. Returns the authorization URL."""
    service = ConnectionService(db)
    try:
        url = await service.initiate_oauth(provider, user_id, request.redirect_uri)
        return OAuthAuthorizeResponse(authorization_url=url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.get("/{provider}/callback", response_model=ConnectionResponse)
async def handle_oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Handle OAuth callback, store credentials, create/update connection."""
    service = ConnectionService(db)
    try:
        connection = await service.handle_oauth_callback(
            provider, user_id, family_id, code, state
        )
        await db.commit()
        return connection
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Soft-delete a connection (set is_active=False)."""
    service = ConnectionService(db)
    try:
        await service.delete_connection(connection_id, user_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )


@router.patch("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: UUID,
    request: UpdateConnectionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Update connection scopes or configuration."""
    service = ConnectionService(db)
    try:
        updates = request.dict(exclude_unset=True)
        connection = await service.update_connection(connection_id, user_id, updates)
        await db.commit()
        return connection
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/{connection_id}/sync", response_model=SyncResponse)
async def trigger_sync(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Trigger a manual sync for a connection (placeholder)."""
    # Placeholder: in production this would enqueue a Celery task
    return SyncResponse(
        message="Sync triggered",
        connection_id=str(connection_id),
    )


@router.post("/custom", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_connection(
    request: CreateCustomConnectionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Create a custom MCP data connection."""
    service = ConnectionService(db)
    try:
        connection = await service.create_connection(
            user_id=user_id,
            family_id=family_id,
            provider_name=request.provider_name,
            display_name=request.display_name,
            auth_type=request.auth_type,
            scopes=request.scopes,
            mcp_server_url=request.mcp_server_url,
            mcp_server_config=request.mcp_server_config,
        )
        await db.commit()
        return connection
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
