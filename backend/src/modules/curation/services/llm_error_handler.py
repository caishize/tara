"""
LLM Error Handler - Provides fallback mechanisms for LLM failures.

This module implements robust error handling for LLM calls, ensuring the system
continues to function even when LLM services are unavailable or return errors.
"""
import asyncio
import json
from typing import Any, Callable, Optional, TypeVar
from ....config.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class LLMErrorHandler:
    """Handles LLM errors and provides fallback mechanisms.

    Wraps LLM calls with timeout handling, format validation,
    and automatic fallback to rule-based engines when LLM fails.
    """

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def call_llm_with_fallback(
        self,
        llm_func: Callable[..., Any],
        fallback_func: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """Call LLM with automatic fallback to rule engine on failure."""
        try:
            result = await asyncio.wait_for(
                llm_func(*args, **kwargs),
                timeout=self.timeout,
            )

            if not self._validate_llm_result(result):
                logger.warning(
                    "LLM result validation failed, using fallback. "
                    f"Result type: {type(result)}"
                )
                return await fallback_func(*args, **kwargs)

            if self._is_empty_result(result):
                logger.info("LLM returned empty result, using fallback")
                return await fallback_func(*args, **kwargs)

            return result

        except asyncio.TimeoutError:
            logger.error(
                f"LLM timeout after {self.timeout}s, using fallback"
            )
            return await fallback_func(*args, **kwargs)

        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON decode error: {e}, using fallback")
            return await fallback_func(*args, **kwargs)

        except Exception as e:
            logger.error(f"LLM error: {e}, using fallback")
            return await fallback_func(*args, **kwargs)

    def _validate_llm_result(self, result: Any) -> bool:
        """Validate that LLM result has expected structure."""
        if result is None:
            return False
        if isinstance(result, list):
            return True
        if isinstance(result, dict):
            return True
        return True

    def _is_empty_result(self, result: Any) -> bool:
        """Check if result is effectively empty."""
        if result is None:
            return True
        if isinstance(result, (list, dict, str)):
            return len(result) == 0
        return False

    async def call_with_retry(
        self,
        func: Callable[..., T],
        max_retries: int = 2,
        *args,
        **kwargs,
    ) -> Optional[T]:
        """Call a function with automatic retry on failure."""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}, retrying..."
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    logger.error(
                        f"All {max_retries + 1} attempts failed. Last error: {e}"
                    )

        return None
