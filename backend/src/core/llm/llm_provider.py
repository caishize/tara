"""
OpenAI LLM adapter implementation using OpenAI Compatible API.

This adapter supports both OpenAI and compatible APIs (like Dashscope/Alibaba Cloud).
Uses the standard OpenAI Chat Completions API for all operations.

For Dashscope API compatibility:
- Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
- Uses standard OpenAI chat.completions API
- Fully supports streaming, tool calling, and embeddings

Originally from adapters/llm/openai_adapter.py, moved to core/llm/.
"""
from typing import List, Dict, Any, AsyncIterator, Optional
import json
from openai import AsyncOpenAI

from ..interfaces.llm_provider import ILLMProvider, LLMMessage, LLMResponse
from ..observability.metrics import llm_token_usage
from ...config.settings import settings
from ...config.logging import get_logger


logger = get_logger(__name__)


def _observe_token_usage(model: str, usage) -> None:
    """Record input/output token counts as histogram observations."""
    if not usage:
        return
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    if prompt_tokens:
        llm_token_usage.labels(model=model, direction="input").observe(prompt_tokens)
    if completion_tokens:
        llm_token_usage.labels(model=model, direction="output").observe(completion_tokens)


class OpenAIAdapter(ILLMProvider):
    """OpenAI adapter using standard OpenAI Compatible API."""

    def __init__(self, api_key: Optional[str] = None):
        client_args = {
            "api_key": api_key or settings.openai_api_key,
            "timeout": 180.0,
        }
        if settings.openai_api_base:
            client_args["base_url"] = settings.openai_api_base

        self.client = AsyncOpenAI(**client_args)
        self.model = settings.llm_model
        self.embedding_model = settings.embedding_model
        self.model_name = self.model

    def _serialize_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """
        Serialize LLMMessage list to OpenAI Chat Completions format.

        Converts internal message format to OpenAI API format:
        - Handles tool messages
        - Handles assistant messages with tool calls
        - Preserves all message roles
        """
        result = []
        for msg in messages:
            if msg.role == "tool":
                # Tool result message
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or "",
                })
            elif msg.role == "assistant" and msg.tool_calls:
                # Assistant message with tool calls
                openai_tool_calls = []
                for tc in msg.tool_calls:
                    openai_tool_calls.append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": tc.get("arguments", "{}") if isinstance(tc.get("arguments"), str) else json.dumps(tc.get("arguments", {})),
                        }
                    })
                result.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": openai_tool_calls,
                })
            else:
                # Regular user/system/assistant message
                result.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })
        return result

    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Chat completion using OpenAI Compatible API."""
        try:
            openai_messages = self._serialize_messages(messages)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            _observe_token_usage(self.model, response.usage)

            return LLMResponse(
                text=response.choices[0].message.content or "",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
                finish_reason=response.choices[0].finish_reason or "stop",
            )

        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            raise

    async def function_call(
        self,
        messages: List[LLMMessage],
        functions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Function calling for structured output (legacy format)."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                functions=functions,
                function_call="auto"
            )

            _observe_token_usage(self.model, response.usage)

            if response.choices[0].message.function_call:
                return {
                    "name": response.choices[0].message.function_call.name,
                    "arguments": json.loads(response.choices[0].message.function_call.arguments)
                }

            return {}

        except Exception as e:
            logger.error(f"OpenAI function call error: {e}")
            raise

    async def chat_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """Chat with tools/function calling support."""
        try:
            openai_messages = self._serialize_messages(messages)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens
            )

            _observe_token_usage(self.model, response.usage)

            message = response.choices[0].message
            result = {
                "content": message.content,
                "tool_calls": [],
                "finish_reason": response.choices[0].finish_reason
            }

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    try:
                        args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse tool arguments: {e}, raw: {tool_call.function.arguments[:200]}...")
                        args = {}
                    result["tool_calls"].append({
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "arguments": args
                    })

            return result

        except Exception as e:
            logger.error(f"OpenAI chat_with_tools error: {e}")
            raise

    async def chat_with_tools_stream(
        self,
        messages: List[LLMMessage],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream chat with tools using OpenAI Compatible streaming API.

        Yields:
        - {"type": "content", "content": "..."} for text content
        - {"type": "tool_call", "id": "...", "name": "...", "arguments": {...}} for tool calls
        - {"type": "done", "finish_reason": "..."} when complete
        """
        try:
            openai_messages = self._serialize_messages(messages)

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            tool_calls_in_progress: Dict[int, Dict[str, Any]] = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # Yield text content
                if delta.content:
                    yield {"type": "content", "content": delta.content}

                # Track tool calls being built
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        idx = tool_call.index
                        if idx not in tool_calls_in_progress:
                            tool_calls_in_progress[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": ""
                            }

                        if tool_call.id:
                            tool_calls_in_progress[idx]["id"] = tool_call.id
                        if tool_call.function:
                            if tool_call.function.name:
                                tool_calls_in_progress[idx]["name"] = tool_call.function.name
                            if tool_call.function.arguments:
                                tool_calls_in_progress[idx]["arguments"] += tool_call.function.arguments

                # When stream finishes, yield all collected tool calls
                if chunk.choices[0].finish_reason:
                    for idx in sorted(tool_calls_in_progress.keys()):
                        tc = tool_calls_in_progress[idx]
                        try:
                            args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield {
                            "type": "tool_call",
                            "id": tc["id"],
                            "name": tc["name"],
                            "arguments": args
                        }

                    yield {"type": "done", "finish_reason": chunk.choices[0].finish_reason}

        except Exception as e:
            logger.error(f"OpenAI chat_with_tools_stream error: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> AsyncIterator[str]:
        """Stream chat completion."""
        try:
            openai_messages = self._serialize_messages(messages)

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI chat_stream error: {e}")
            raise

    async def embed(self, text: str) -> List[float]:
        """Generate text embedding."""
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise

    async def get_embedding(self, text: str) -> List[float]:
        """Alias for embed() - for compatibility."""
        return await self.embed(text)

    async def get_embeddings_batch(
        self, texts: List[str], *, max_batch_size: int = 10
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts, automatically chunked.

        DashScope limits batch size to 10. This method transparently splits
        larger inputs into sequential batches and concatenates the results.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        for start in range(0, len(texts), max_batch_size):
            batch = texts[start:start + max_batch_size]
            try:
                response = await self.client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )
                sorted_data = sorted(response.data, key=lambda x: x.index)
                all_embeddings.extend(
                    item.embedding for item in sorted_data
                )
            except Exception as e:
                logger.error(
                    f"Batch embedding failed (offset={start}, "
                    f"size={len(batch)}): {e}"
                )
                raise

        return all_embeddings

    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Simple text generation."""
        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return response.text


# Global instance
openai_adapter = OpenAIAdapter()
