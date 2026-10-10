"""
Test DashScope integration with Anthropic-compatible API.

This test verifies that the custom base_url configuration works correctly
with DashScope/Aliyun's Anthropic-compatible endpoint.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Test configuration loading
class TestDashScopeConfiguration:
    """Test that DashScope configuration is loaded correctly."""

    def test_settings_load_anthropic_base_url(self):
        """Test that anthropic_base_url is loaded from environment."""
        from src.config.settings import Settings

        with patch.dict('os.environ', {
            'ANTHROPIC_API_KEY': 'test-key',
            'ANTHROPIC_BASE_URL': 'https://dashscope.aliyuncs.com/apps/anthropic',
            'ANTHROPIC_MODEL': 'qwen3-max-2026-01-23',
        }):
            settings = Settings()
            assert settings.anthropic_api_key == 'test-key'
            assert settings.anthropic_base_url == 'https://dashscope.aliyuncs.com/apps/anthropic'
            assert settings.anthropic_model == 'qwen3-max-2026-01-23'

    def test_effective_anthropic_model_uses_anthropic_model(self):
        """Test effective_anthropic_model returns anthropic_model when claude_model is empty."""
        from src.config.settings import Settings

        with patch.dict('os.environ', {
            'ANTHROPIC_MODEL': 'qwen3-max-2026-01-23',
            'CLAUDE_MODEL': '',
        }):
            settings = Settings()
            assert settings.effective_anthropic_model == 'qwen3-max-2026-01-23'

    def test_effective_anthropic_model_backwards_compatible(self):
        """Test effective_anthropic_model respects CLAUDE_MODEL for backwards compatibility."""
        from src.config.settings import Settings

        with patch.dict('os.environ', {
            'ANTHROPIC_MODEL': 'qwen3-max-2026-01-23',
            'CLAUDE_MODEL': 'claude-3-opus-20240229',
        }):
            settings = Settings()
            # CLAUDE_MODEL takes precedence for backwards compatibility
            assert settings.effective_anthropic_model == 'claude-3-opus-20240229'


class TestAnthropicClientCreation:
    """Test that Anthropic clients are created with correct configuration."""

    def test_intent_router_uses_base_url(self):
        """Test IntentRouter uses custom base_url."""
        with patch.dict('os.environ', {
            'ANTHROPIC_API_KEY': 'test-key',
            'ANTHROPIC_BASE_URL': 'https://dashscope.aliyuncs.com/apps/anthropic',
            'ANTHROPIC_MODEL': 'qwen3-max-2026-01-23',
        }):
            from importlib import reload
            import src.config.settings as settings_module
            reload(settings_module)
            # Also reload settings reference in haiku_client and reset singleton
            import src.core.llm.haiku_client as haiku_module
            reload(haiku_module)
            haiku_module._haiku_client = None

            from src.ai_engine.router.intent_router import IntentRouter

            with patch('src.core.llm.haiku_client.AsyncAnthropic') as mock_client:
                mock_client.return_value = MagicMock()
                router = IntentRouter()
                # Access client property to trigger creation
                _ = router.client

                mock_client.assert_called_once()
                call_kwargs = mock_client.call_args[1]
                assert call_kwargs.get('base_url') == 'https://dashscope.aliyuncs.com/apps/anthropic'

    def test_fast_worker_uses_base_url(self):
        """Test FastWorker uses custom base_url."""
        try:
            import claude_code_sdk  # noqa: F401
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        with patch.dict('os.environ', {
            'ANTHROPIC_API_KEY': 'test-key',
            'ANTHROPIC_BASE_URL': 'https://dashscope.aliyuncs.com/apps/anthropic',
            'ANTHROPIC_MODEL': 'qwen3-max-2026-01-23',
        }):
            from importlib import reload
            import src.config.settings as settings_module
            reload(settings_module)

            from src.ai_engine.workers.fast_worker import FastWorker

            with patch('src.ai_engine.workers.fast_worker.AsyncAnthropic') as mock_client:
                worker = FastWorker()
                # Access client property to trigger creation
                _ = worker.client

                mock_client.assert_called_once()
                call_kwargs = mock_client.call_args[1]
                assert call_kwargs.get('base_url') == 'https://dashscope.aliyuncs.com/apps/anthropic'


@pytest.mark.asyncio
@pytest.mark.skipif(
    not __import__('os').getenv('DASHSCOPE_INTEGRATION_TEST'),
    reason="Set DASHSCOPE_INTEGRATION_TEST=1 to run live DashScope API tests"
)
class TestDashScopeAPICall:
    """Integration tests for actual DashScope API calls."""

    async def test_simple_chat_completion(self):
        """Test a simple chat completion with DashScope."""
        from src.config.settings import settings

        # Skip if not configured
        if not settings.anthropic_base_url:
            pytest.skip("ANTHROPIC_BASE_URL not configured")

        if not settings.anthropic_api_key:
            pytest.skip("ANTHROPIC_API_KEY not configured")

        from anthropic import AsyncAnthropic

        client_kwargs = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            client_kwargs["base_url"] = settings.anthropic_base_url

        client = AsyncAnthropic(**client_kwargs)

        try:
            response = await client.messages.create(
                model=settings.effective_anthropic_model,
                max_tokens=100,
                messages=[
                    {"role": "user", "content": "Say 'Hello' in Chinese. Just respond with the greeting, nothing else."}
                ],
            )

            assert response.content
            assert len(response.content) > 0
            content = response.content[0].text
            print(f"\nDashScope Response: {content}")
            assert "你好" in content or "您好" in content or "Hello" in content.lower()

        except Exception as e:
            pytest.fail(f"DashScope API call failed: {e}")

    async def test_streaming_chat_completion(self):
        """Test streaming chat completion with DashScope."""
        from src.config.settings import settings

        # Skip if not configured
        if not settings.anthropic_base_url:
            pytest.skip("ANTHROPIC_BASE_URL not configured")

        if not settings.anthropic_api_key:
            pytest.skip("ANTHROPIC_API_KEY not configured")

        from anthropic import AsyncAnthropic

        client_kwargs = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            client_kwargs["base_url"] = settings.anthropic_base_url

        client = AsyncAnthropic(**client_kwargs)

        try:
            collected_content = []

            async with client.messages.stream(
                model=settings.effective_anthropic_model,
                max_tokens=100,
                messages=[
                    {"role": "user", "content": "Count from 1 to 5 in Chinese."}
                ],
            ) as stream:
                async for text in stream.text_stream:
                    collected_content.append(text)
                    print(text, end="", flush=True)

            print()  # newline
            full_response = "".join(collected_content)
            assert len(full_response) > 0
            # Should contain Chinese numbers
            assert any(char in full_response for char in ["一", "二", "三", "四", "五", "1", "2", "3", "4", "5"])

        except Exception as e:
            pytest.fail(f"DashScope streaming API call failed: {e}")


if __name__ == "__main__":
    # Run integration tests directly
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    print("=" * 60)
    print("Testing DashScope Integration")
    print("=" * 60)

    from src.config.settings import settings

    print(f"\nConfiguration:")
    print(f"  ANTHROPIC_API_KEY: {'*' * 8}...{settings.anthropic_api_key[-4:] if settings.anthropic_api_key else 'NOT SET'}")
    print(f"  ANTHROPIC_BASE_URL: {settings.anthropic_base_url or 'NOT SET'}")
    print(f"  ANTHROPIC_MODEL: {settings.effective_anthropic_model}")
    print()

    if not settings.anthropic_base_url or not settings.anthropic_api_key:
        print("ERROR: DashScope configuration not set. Please configure:")
        print("  ANTHROPIC_API_KEY=your-dashscope-api-key")
        print("  ANTHROPIC_BASE_URL=https://dashscope.aliyuncs.com/apps/anthropic")
        print("  ANTHROPIC_MODEL=qwen3-max-2026-01-23")
        sys.exit(1)

    print("Running simple API test...")
    asyncio.run(TestDashScopeAPICall().test_simple_chat_completion())

    print("\nRunning streaming API test...")
    asyncio.run(TestDashScopeAPICall().test_streaming_chat_completion())

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
