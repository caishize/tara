#!/usr/bin/env python3
"""
Test script for Dashscope Responses API integration.

Usage:
    # Test with Dashscope
    LLM_PROVIDER=dashscope DASHSCOPE_API_KEY=sk-xxx python backend/scripts/test_dashscope.py

    # Test with OpenAI
    LLM_PROVIDER=openai OPENAI_API_KEY=sk-xxx python backend/scripts/test_dashscope.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from src.adapters.llm.provider_factory import get_llm_provider
from src.core.interfaces.llm_provider import LLMMessage


async def test_basic_chat(llm):
    """Test basic chat completion."""
    print("\n=== Test 1: Basic Chat ===")
    messages = [
        LLMMessage(role="user", content="Say hello in exactly 3 words")
    ]
    response = await llm.chat(messages)
    print(f"Response: {response.text}")
    print(f"Tokens: {response.usage}")
    print(f"Finish reason: {response.finish_reason}")


async def test_streaming(llm):
    """Test streaming chat completion."""
    print("\n=== Test 2: Streaming ===")
    messages = [
        LLMMessage(role="user", content="What is artificial intelligence?")
    ]
    print("Response: ", end='', flush=True)
    async for chunk in llm.chat_stream(messages):
        print(chunk, end='', flush=True)
    print()


async def test_tool_calling(llm):
    """Test tool calling."""
    print("\n=== Test 3: Tool Calling ===")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather information for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
                    },
                    "required": ["location"]
                }
            }
        }
    ]

    messages = [
        LLMMessage(role="user", content="What's the weather like in Beijing?")
    ]

    result = await llm.chat_with_tools(messages, tools)
    print(f"Content: {result.get('content', '')}")
    print(f"Tool calls: {result.get('tool_calls', [])}")
    print(f"Finish reason: {result.get('finish_reason', '')}")


async def test_streaming_tools(llm):
    """Test streaming with tool calling."""
    print("\n=== Test 4: Streaming with Tools ===")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    messages = [
        LLMMessage(role="user", content="Search for the latest AI news")
    ]

    print("Streaming response:\n")
    async for event in llm.chat_with_tools_stream(messages, tools):
        if event["type"] == "content":
            print(event["content"], end='', flush=True)
        elif event["type"] == "tool_call":
            print(f"\n\n[Tool Call] {event['name']}: {event['arguments']}")
        elif event["type"] == "status":
            print(f"\n[Status: {event['status']}]")
        elif event["type"] == "done":
            print(f"\n\nDone! Finish reason: {event['finish_reason']}")


async def test_embeddings(llm):
    """Test embedding generation."""
    print("\n=== Test 5: Embeddings ===")
    text = "Artificial intelligence is transforming the world"
    embedding = await llm.embed(text)
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")

    texts = ["Hello", "World", "AI"]
    embeddings = await llm.get_embeddings_batch(texts)
    print(f"\nBatch embeddings: {len(embeddings)} vectors")
    for i, emb in enumerate(embeddings):
        print(f"  Text {i}: '{texts[i]}' -> dim {len(emb)}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Dashscope Responses API Test Suite")
    print("=" * 60)

    try:
        # Get LLM provider based on environment configuration
        llm = get_llm_provider()
        provider_type = type(llm).__name__
        print(f"\nUsing provider: {provider_type}")
        print(f"Model: {llm.model_name}")

        # Run tests
        await test_basic_chat(llm)
        await test_streaming(llm)
        await test_tool_calling(llm)
        # await test_streaming_tools(llm)  # Uncomment to test streaming with tools
        await test_embeddings(llm)

        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
