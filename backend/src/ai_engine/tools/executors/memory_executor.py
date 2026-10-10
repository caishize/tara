"""Memory domain tool executor — memory search, save, update, and execution details."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from ....config.logging import get_logger
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)


from ..shared.sql_utils import escape_like as _escape_like


class MemoryToolExecutor(BaseToolExecutor):
    """Handles search_memory, save_memory, update_memory, view_execution_details."""

    # ------------------------------------------------------------------
    # Memory search
    # ------------------------------------------------------------------

    async def search_memories(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from sqlalchemy import select, and_, or_
        from ....modules.memory.models import ConversationMemory

        query = args.get("query", "")
        memory_type = args.get("memory_type")
        person = args.get("person")
        date_range = args.get("date_range")

        try:
            conditions = [
                ConversationMemory.family_id == family_id,
                ConversationMemory.status == "active",
            ]

            if query:
                safe_query = _escape_like(query)
                conditions.append(
                    or_(
                        ConversationMemory.content.ilike(f"%{safe_query}%", escape="\\"),
                        ConversationMemory.summary.ilike(f"%{safe_query}%", escape="\\"),
                    )
                )

            if memory_type:
                conditions.append(ConversationMemory.memory_type == memory_type)

            if person:
                safe_person = _escape_like(person)
                conditions.append(
                    or_(
                        ConversationMemory.entities["person"].astext.ilike(f"%{safe_person}%", escape="\\"),
                        ConversationMemory.content.ilike(f"%{safe_person}%", escape="\\"),
                    )
                )

            if date_range:
                from datetime import timedelta

                from ....core.utils.timezone import utc_now
                now = utc_now()
                if date_range == "today":
                    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    conditions.append(ConversationMemory.created_at >= start)
                elif date_range == "week":
                    conditions.append(ConversationMemory.created_at >= now - timedelta(days=7))
                elif date_range == "month":
                    conditions.append(ConversationMemory.created_at >= now - timedelta(days=30))

            stmt = (
                select(ConversationMemory)
                .where(and_(*conditions))
                .order_by(ConversationMemory.importance.desc(), ConversationMemory.created_at.desc())
                .limit(20)
            )

            result = await self.db.execute(stmt)
            memories = list(result.scalars().all())

            # Always supplement with current session conversation search
            session_messages = []
            if self.session_id:
                try:
                    from ....modules.conversation.models import ConversationMessage as CM

                    msg_stmt = (
                        select(CM)
                        .where(
                            CM.session_id == self.session_id,
                            CM.role.in_(["user", "assistant"]),
                        )
                        .order_by(CM.created_at.desc())
                        .limit(10)
                    )
                    if query:
                        safe_session_query = _escape_like(query)
                        msg_stmt = msg_stmt.where(
                            CM.content.ilike(f"%{safe_session_query}%", escape="\\")
                        )
                    msg_result = await self.db.execute(msg_stmt)
                    session_messages = list(msg_result.scalars().all())
                except Exception as e:
                    logger.warning("Session message search failed: %s", e)

            session_context = [
                {
                    "role": m.role,
                    "content": m.content[:200] if m.content else "",
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in session_messages
            ] if session_messages else []

            if not memories:
                filters = []
                if query:
                    filters.append(f"关键词「{query}」")
                if memory_type:
                    filters.append(f"类型「{memory_type}」")
                if person:
                    filters.append(f"相关人物「{person}」")
                filter_desc = "、".join(filters) if filters else "当前条件"

                return {
                    "success": True,
                    "memories": [],
                    "total_count": 0,
                    "session_context": session_context,
                    "message": (
                        f"没有找到符合{filter_desc}的长期记忆"
                        + (f"，但在当前会话中找到 {len(session_context)} 条相关对话" if session_context else "")
                    ),
                }

            memory_list = [
                {
                    "id": str(m.id),
                    "memory_type": m.memory_type,
                    "summary": m.summary,
                    "content": m.content[:200] + "..." if len(m.content) > 200 else m.content,
                    "entities": m.entities or {},
                    "tags": m.tags or [],
                    "importance": m.importance,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in memories
            ]

            return {
                "success": True,
                "memories": memory_list,
                "total_count": len(memory_list),
                "session_context": session_context,
                "message": f"找到 {len(memory_list)} 条相关记忆",
            }

        except Exception as e:
            logger.error("Search memories failed: %s", e)
            return {"success": False, "message": "搜索记忆失败，请稍后重试"}

    # ------------------------------------------------------------------
    # Memory save / update
    # ------------------------------------------------------------------

    async def save_memory(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Save a new memory record from agent conversation."""
        from sqlalchemy import select
        from ....modules.memory.models import ConversationMemory
        from ....core.utils.timezone import utc_now

        content = args.get("content", "")
        summary = args.get("summary", "")
        memory_type = args.get("memory_type", "general")
        person = args.get("person")
        importance = args.get("importance", 5)
        tags = args.get("tags", [])

        if not content:
            return {"success": False, "message": "记忆内容不能为空"}

        try:
            entities: Dict[str, Any] = {}
            if person:
                entities["person"] = person

            memory = ConversationMemory(
                family_id=family_id,
                user_id=user_id,
                content=content,
                summary=summary or content[:100],
                memory_type=memory_type,
                entities=entities,
                tags=tags,
                importance=min(max(importance, 1), 10),
                status="active",
                created_at=utc_now(),
            )

            self.db.add(memory)
            await self.db.commit()
            await self.db.refresh(memory)

            # Auto-extract contacts for person-related memories
            await self._auto_extract_contacts_from_saved(
                user_id=user_id,
                family_id=family_id,
                memory=memory,
            )

            return {
                "success": True,
                "memory_id": str(memory.id),
                "summary": memory.summary,
                "message": f"已保存记忆: {memory.summary[:50]}",
            }
        except Exception as e:
            logger.error("Save memory failed: %s", e)
            await self.db.rollback()
            return {"success": False, "message": "保存记忆失败，请稍后重试"}

    async def _auto_extract_contacts_from_saved(
        self,
        user_id: UUID,
        family_id: UUID,
        memory: "ConversationMemory",
    ) -> None:
        """Trigger auto contact extraction after save_memory creates a memory."""
        try:
            entities = memory.entities or {}
            if not entities.get("person") and not entities.get("persons"):
                return

            from ....modules.memory.auto_contact_extraction_service import (
                AutoContactExtractionService,
            )

            service = AutoContactExtractionService(self.db)
            created = await service.extract_contacts_from_memories(
                user_id=user_id,
                family_id=family_id,
                memories=[memory],
            )
            if created:
                names = [c[0].name for c in created]
                logger.info(
                    "Auto-extracted %d contact(s) from save_memory: %s",
                    len(created),
                    ", ".join(names),
                )
        except Exception as e:
            logger.error("Auto contact extraction after save_memory failed: %s", e)

    async def update_memory(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Update an existing memory record."""
        from sqlalchemy import select
        from ....modules.memory.models import ConversationMemory

        memory_id_str = args.get("memory_id", "")
        updates = args.get("updates", {})

        if not memory_id_str:
            return {"success": False, "message": "缺少 memory_id 参数"}

        try:
            memory_id = UUID(memory_id_str)
        except ValueError:
            return {"success": False, "message": f"无效的 memory_id: {memory_id_str}"}

        if not updates:
            return {"success": False, "message": "没有提供要更新的内容"}

        try:
            stmt = select(ConversationMemory).where(
                ConversationMemory.id == memory_id,
                ConversationMemory.family_id == family_id,
                ConversationMemory.status == "active",
            )
            result = await self.db.execute(stmt)
            memory = result.scalar_one_or_none()

            if not memory:
                return {"success": False, "message": "记忆未找到或已被删除"}

            if "content" in updates:
                memory.content = updates["content"]
            if "summary" in updates:
                memory.summary = updates["summary"]
            if "memory_type" in updates:
                memory.memory_type = updates["memory_type"]
            if "importance" in updates:
                memory.importance = min(max(updates["importance"], 1), 10)
            if "tags" in updates:
                memory.tags = updates["tags"]
            if "status" in updates and updates["status"] in ("active", "archived", "superseded"):
                memory.status = updates["status"]

            await self.db.commit()

            return {
                "success": True,
                "memory_id": str(memory.id),
                "updated_fields": list(updates.keys()),
                "message": f"已更新记忆: {memory.summary[:50]}",
            }
        except Exception as e:
            logger.error("Update memory failed: %s", e)
            await self.db.rollback()
            return {"success": False, "message": "更新记忆失败，请稍后重试"}

    # ------------------------------------------------------------------
    # Execution details (superseded by view_tool_details in recall_executor)
    # ------------------------------------------------------------------

    async def view_execution_details(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        execution_id = args.get("execution_id", "")
        include_logs = args.get("include_logs", False)

        # The execution_store is set on the executor by ToolBridge
        execution_store = getattr(self, "_execution_store", None)

        if not execution_store:
            return {
                "error": "工具执行记录不可用",
                "hint": "只有在当前会话中执行过的工具才有记录",
            }

        record = execution_store.get_execution(execution_id)
        if not record:
            available = [r.execution_id for r in execution_store.get_all_executions()]
            return {
                "error": f"未找到执行记录: {execution_id}",
                "available_executions": available[:10],
                "hint": "请使用【工具执行记录】中显示的执行ID",
            }

        details = record.get_full_details()
        if not include_logs:
            details.pop("logs", None)

        return {
            "execution_id": execution_id,
            "details": details,
            "note": "这是完整的执行详情，包含原始结果数据",
        }
