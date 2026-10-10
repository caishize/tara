"""MCP domain tool executor — 2 tools for MCP tool invocation."""

from typing import Any, Dict, Optional
from uuid import UUID

from ....config.logging import get_logger
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)


class McpToolExecutor(BaseToolExecutor):
    """Handles call_mcp_tool and list_mcp_tools."""

    async def call_mcp_tool(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        try:
            from ....modules.data_connection.services.connection_manager import DataConnectionManager
            from ....core.interfaces.data_connector import get_connector_class

            connector_id = args.get("connector_id")
            tool_name = args.get("tool_name")
            tool_args = args.get("arguments", {})

            if not connector_id:
                return {"success": False, "message": "请指定 MCP 连接器 ID"}

            if not tool_name:
                return {"success": False, "message": "请指定要调用的工具名称"}

            manager = DataConnectionManager(self.db)

            connections = await manager.get_user_connections(user_id)
            connection = next(
                (c for c in connections if c.connector_id == connector_id and c.status == "connected"),
                None,
            )

            if not connection:
                return {
                    "success": False,
                    "message": f"未连接到 {connector_id}。请先在【数据连接中心】添加此连接。",
                }

            connector_class = get_connector_class(connector_id)
            if not connector_class:
                return {"success": False, "message": f"连接器 {connector_id} 不存在"}

            connector = connector_class()

            if not hasattr(connector, "call_tool"):
                return {"success": False, "message": f"连接器 {connector_id} 不支持工具调用"}

            credentials = await manager.vault.retrieve_credentials(connection.id, connection.family_id)

            if not credentials:
                return {"success": False, "message": "凭据已过期，请在【数据连接中心】重新连接"}

            result = await connector.call_tool(credentials, tool_name, tool_args)

            return {
                "success": True,
                "connector_id": connector_id,
                "tool_name": tool_name,
                "result": result,
                "message": f"已执行 MCP 工具: {tool_name}",
            }

        except ImportError:
            return {"success": False, "message": "数据连接模块未启用"}
        except Exception as e:
            logger.error(f"Call MCP tool failed: {e}")
            return {"success": False, "message": f"调用 MCP 工具失败: {str(e)}"}

    async def list_mcp_tools(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        try:
            from ....modules.data_connection.services.connection_manager import DataConnectionManager
            from ....core.interfaces.data_connector import get_connector_class, AuthType

            connector_id = args.get("connector_id")

            manager = DataConnectionManager(self.db)
            connections = await manager.get_user_connections(user_id)

            mcp_connections = [c for c in connections if c.status == "connected"]

            if connector_id:
                mcp_connections = [c for c in mcp_connections if c.connector_id == connector_id]

            if not mcp_connections:
                return {
                    "success": True,
                    "tools": [],
                    "message": "未找到已连接的 MCP 服务器。请在【数据连接中心】添加 MCP 连接。",
                }

            all_tools = []
            for conn in mcp_connections:
                connector_class = get_connector_class(conn.connector_id)
                if not connector_class:
                    continue

                connector = connector_class()

                if connector.metadata.auth_type != AuthType.MCP:
                    continue

                if not hasattr(connector, "get_available_tools"):
                    continue

                credentials = await manager.vault.retrieve_credentials(conn.id, conn.family_id)

                if not credentials:
                    continue

                try:
                    await connector.test_connection(credentials)
                    tools = connector.get_available_tools()

                    for tool in tools:
                        all_tools.append({
                            "connector_id": conn.connector_id,
                            "connector_name": conn.connector_name,
                            "tool_name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.input_schema,
                        })
                except Exception as e:
                    logger.warning(f"Failed to get tools from {conn.connector_id}: {e}")

            return {
                "success": True,
                "tools": all_tools,
                "total": len(all_tools),
                "message": f"找到 {len(all_tools)} 个可用的 MCP 工具" if all_tools else "没有可用的 MCP 工具",
            }

        except ImportError:
            return {"success": False, "message": "数据连接模块未启用"}
        except Exception as e:
            logger.error(f"List MCP tools failed: {e}")
            return {"success": False, "message": f"列出 MCP 工具失败: {str(e)}"}
