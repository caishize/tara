"""
事件处理器注册表

负责发现、注册和管理所有事件处理器。
"""

import logging
import importlib
import inspect
from typing import Dict, List, Callable, Type, Any, Optional
from pathlib import Path

from ..event_bus import EventBus, DomainEvent, get_event_bus

logger = logging.getLogger(__name__)


class HandlerRegistry:
    """
    事件处理器注册表

    管理事件处理器的注册和依赖注入。
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._registered_handlers: Dict[str, Callable] = {}
        self._handler_factories: Dict[str, Callable] = {}

    def register_handler(
        self,
        event_type: Type[DomainEvent],
        handler: Callable,
        is_async: bool = True
    ) -> None:
        """
        注册事件处理器

        Args:
            event_type: 事件类型
            handler: 处理函数
            is_async: 是否异步处理
        """
        handler_name = f"{event_type.__name__}:{handler.__name__}"
        if handler_name in self._registered_handlers:
            logger.warning(f"Handler already registered: {handler_name}")
            return

        self.event_bus.subscribe(event_type, handler, is_async)
        self._registered_handlers[handler_name] = handler
        logger.info(f"Registered handler: {handler_name}")

    def register_handler_factory(
        self,
        event_type: Type[DomainEvent],
        factory: Callable,
        is_async: bool = True
    ) -> None:
        """
        注册处理器工厂

        工厂函数接收依赖并返回处理函数。

        Args:
            event_type: 事件类型
            factory: 工厂函数
            is_async: 是否异步处理
        """
        factory_name = f"{event_type.__name__}:{factory.__name__}"
        self._handler_factories[factory_name] = {
            'event_type': event_type,
            'factory': factory,
            'is_async': is_async
        }
        logger.debug(f"Registered handler factory: {factory_name}")

    def initialize_factories(self, dependencies: Dict[str, Any]) -> None:
        """
        使用依赖初始化所有工厂

        Args:
            dependencies: 依赖字典 {name: instance}
        """
        for factory_name, factory_info in self._handler_factories.items():
            try:
                factory = factory_info['factory']
                event_type = factory_info['event_type']
                is_async = factory_info['is_async']

                # 解析工厂函数所需的依赖
                sig = inspect.signature(factory)
                kwargs = {}
                for param_name, param in sig.parameters.items():
                    if param_name in dependencies:
                        kwargs[param_name] = dependencies[param_name]

                # 创建处理器
                handler = factory(**kwargs)
                self.register_handler(event_type, handler, is_async)
                logger.info(f"Initialized factory handler: {factory_name}")

            except Exception as e:
                logger.error(f"Failed to initialize factory {factory_name}: {e}")

    def get_registered_handlers(self) -> List[str]:
        """获取所有已注册的处理器名称"""
        return list(self._registered_handlers.keys())


def discover_handlers(module_path: str) -> List[Callable]:
    """
    发现模块中所有标记了 @event_handler 的函数

    Args:
        module_path: 模块路径

    Returns:
        处理器函数列表
    """
    handlers = []
    try:
        module = importlib.import_module(module_path)
        for name, obj in inspect.getmembers(module):
            if callable(obj) and hasattr(obj, '_event_handler_info'):
                handlers.append(obj)
    except ImportError as e:
        logger.error(f"Failed to import module {module_path}: {e}")
    return handlers


def register_all_handlers(
    event_bus: Optional[EventBus] = None,
    dependencies: Optional[Dict[str, Any]] = None
) -> HandlerRegistry:
    """
    注册所有事件处理器

    Args:
        event_bus: 事件总线实例
        dependencies: 依赖字典

    Returns:
        处理器注册表
    """
    if event_bus is None:
        event_bus = get_event_bus()

    registry = HandlerRegistry(event_bus)

    # 导入处理器模块
    handler_modules = [
        'src.core.events.handlers.date_handlers',
        'src.core.events.handlers.gift_handlers',
        'src.core.events.handlers.feedback_handlers',
    ]

    for module_path in handler_modules:
        try:
            handlers = discover_handlers(module_path)
            for handler in handlers:
                info = handler._event_handler_info
                registry.register_handler(
                    info['event_type'],
                    handler,
                    info['is_async']
                )
        except Exception as e:
            logger.warning(f"Could not load handlers from {module_path}: {e}")

    # 初始化工厂
    if dependencies:
        registry.initialize_factories(dependencies)

    logger.info(f"Registered {len(registry.get_registered_handlers())} event handlers")
    return registry
