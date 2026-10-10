"""
Event Bus - 进程内事件总线实现

支持异步事件发布和订阅，用于模块间解耦通信。
"""

import asyncio
import logging
from typing import Dict, List, Callable, Type, Any, Optional
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID, uuid4
from abc import ABC

from ..utils.timezone import utc_now

logger = logging.getLogger(__name__)


@dataclass
class DomainEvent(ABC):
    """领域事件基类"""
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        """序列化为字典，用于日志记录"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, date):
                result[key] = value.isoformat()
            elif hasattr(value, 'value'):  # Enum
                result[key] = value.value
            else:
                result[key] = value
        return result

    @property
    def event_type(self) -> str:
        """事件类型名称"""
        return self.__class__.__name__


EventHandler = Callable[[DomainEvent], Any]


class EventBus:
    """
    进程内事件总线

    支持:
    - 同步/异步事件处理
    - 多处理器订阅同一事件
    - 处理器异常隔离
    - 事件日志记录
    """

    _instance: Optional['EventBus'] = None

    def __init__(self):
        self._handlers: Dict[Type[DomainEvent], List[EventHandler]] = {}
        self._async_handlers: Dict[Type[DomainEvent], List[Callable]] = {}
        self._enabled: bool = True

    @classmethod
    def get_instance(cls) -> 'EventBus':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        cls._instance = None

    def subscribe(
        self,
        event_type: Type[DomainEvent],
        handler: EventHandler,
        is_async: bool = True
    ) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 处理函数
            is_async: 是否异步处理
        """
        if is_async:
            if event_type not in self._async_handlers:
                self._async_handlers[event_type] = []
            if handler not in self._async_handlers[event_type]:
                self._async_handlers[event_type].append(handler)
                logger.debug(f"Subscribed async handler {handler.__name__} to {event_type.__name__}")
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                logger.debug(f"Subscribed sync handler {handler.__name__} to {event_type.__name__}")

    def unsubscribe(
        self,
        event_type: Type[DomainEvent],
        handler: EventHandler
    ) -> None:
        """取消订阅"""
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
        if event_type in self._async_handlers and handler in self._async_handlers[event_type]:
            self._async_handlers[event_type].remove(handler)

    async def publish(self, event: DomainEvent) -> None:
        """
        发布事件

        Args:
            event: 领域事件
        """
        if not self._enabled:
            logger.debug(f"Event bus disabled, skipping event: {event.event_type}")
            return

        event_type = type(event)
        logger.info(f"Publishing event: {event.event_type}", extra={"event_data": event.to_dict()})

        # 执行同步处理器
        sync_handlers = self._handlers.get(event_type, [])
        for handler in sync_handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    f"Error in sync handler {handler.__name__} for {event.event_type}: {e}",
                    exc_info=True
                )

        # 执行异步处理器
        async_handlers = self._async_handlers.get(event_type, [])
        for handler in async_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Error in async handler {handler.__name__} for {event.event_type}: {e}",
                    exc_info=True
                )

    def publish_sync(self, event: DomainEvent) -> None:
        """
        同步发布事件（用于非异步上下文）

        仅执行同步处理器，异步处理器将被跳过。
        """
        if not self._enabled:
            return

        event_type = type(event)
        logger.info(f"Publishing event (sync): {event.event_type}")

        sync_handlers = self._handlers.get(event_type, [])
        for handler in sync_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error in handler {handler.__name__} for {event.event_type}: {e}",
                    exc_info=True
                )

    def enable(self) -> None:
        """启用事件总线"""
        self._enabled = True
        logger.info("Event bus enabled")

    def disable(self) -> None:
        """禁用事件总线"""
        self._enabled = False
        logger.info("Event bus disabled")

    def clear_handlers(self) -> None:
        """清除所有处理器（用于测试）"""
        self._handlers.clear()
        self._async_handlers.clear()

    async def publish_with_outbox(
        self,
        db: 'AsyncSession',
        event: DomainEvent,
    ) -> None:
        """Publish event via Transactional Outbox + in-process handlers.

        Writes the event to the ``event_outbox`` table within the caller's
        DB transaction **and** dispatches to in-process handlers. The outbox
        relay will later publish the event to Redis Streams for cross-process
        consumers.

        Args:
            db: An active async session (caller manages commit/rollback).
            event: The domain event to publish.
        """
        if not self._enabled:
            logger.debug("Event bus disabled, skipping event: %s", event.event_type)
            return

        # 1. Persist to outbox (same transaction as business data)
        from .outbox import save_to_outbox
        await save_to_outbox(db, event)

        # 2. Also fire in-process handlers
        await self.publish(event)

    def get_handler_count(self, event_type: Type[DomainEvent]) -> int:
        """获取某事件类型的处理器数量"""
        sync_count = len(self._handlers.get(event_type, []))
        async_count = len(self._async_handlers.get(event_type, []))
        return sync_count + async_count


def get_event_bus() -> EventBus:
    """获取事件总线单例"""
    return EventBus.get_instance()


def event_handler(event_type: Type[DomainEvent], is_async: bool = True):
    """
    事件处理器装饰器

    用于标记函数为特定事件的处理器，在应用启动时自动注册。

    Usage:
        @event_handler(ImportantDateCreated)
        async def on_date_created(event: ImportantDateCreated):
            # 处理事件
            pass
    """
    def decorator(func: Callable):
        # 标记函数的元信息
        func._event_handler_info = {
            'event_type': event_type,
            'is_async': is_async
        }
        return func
    return decorator
