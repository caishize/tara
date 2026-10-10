"""
事件处理器模块

自动发现和注册所有事件处理器。
"""

from .registry import HandlerRegistry, register_all_handlers
from .stream_consumers import register_stream_consumers

__all__ = ['HandlerRegistry', 'register_all_handlers', 'register_stream_consumers']
