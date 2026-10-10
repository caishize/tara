"""
Unit tests for PriceServiceProvider (unified price service)
Tests provider selection, price fetching across platforms.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.modules.gift.providers import (
    PriceServiceProvider,
    create_price_service,
    Platform,
    PlatformNotSupportedError,
    PriceData,
)
from src.modules.gift.providers.anti_crawler import AntiCrawlerManager, AntiCrawlerConfig


@pytest.fixture
def mock_anti_crawler():
    """Create mock anti-crawler manager that doesn't wait"""
    config = AntiCrawlerConfig(base_delay_min=0, base_delay_max=0.001)
    manager = AntiCrawlerManager(config)
    return manager


@pytest.fixture
def price_service(mock_anti_crawler):
    """Create price service with mock anti-crawler"""
    return PriceServiceProvider(anti_crawler=mock_anti_crawler, timeout=5.0)


class TestPriceServiceCreation:
    """Test price service creation"""

    def test_create_price_service_factory(self):
        """Test factory function creates service"""
        service = create_price_service(timeout=10.0)
        assert isinstance(service, PriceServiceProvider)
        assert service.timeout == 10.0

    def test_create_price_service_default_config(self):
        """Test default configuration"""
        service = create_price_service()
        assert service.timeout == 10.0
        assert service.anti_crawler is not None

    def test_create_with_custom_anti_crawler(self, mock_anti_crawler):
        """Test creating with custom anti-crawler"""
        service = PriceServiceProvider(anti_crawler=mock_anti_crawler)
        assert service.anti_crawler is mock_anti_crawler


class TestProviderSelection:
    """Test automatic provider selection based on URL"""

    def test_jd_url_selects_jd_provider(self, price_service):
        """Test JD URL selects JD provider"""
        provider = price_service._get_provider(Platform.JD)
        assert provider.platform == Platform.JD

    def test_taobao_url_selects_taobao_provider(self, price_service):
        """Test Taobao URL selects Taobao provider"""
        provider = price_service._get_provider(Platform.TAOBAO)
        assert provider.platform == Platform.TAOBAO

    def test_tmall_url_selects_tmall_provider(self, price_service):
        """Test Tmall URL selects Tmall provider"""
        provider = price_service._get_provider(Platform.TMALL)
        assert provider.platform == Platform.TMALL

    def test_pdd_url_selects_pdd_provider(self, price_service):
        """Test PDD URL selects PDD provider"""
        provider = price_service._get_provider(Platform.PDD)
        assert provider.platform == Platform.PDD

    def test_unknown_platform_raises_error(self, price_service):
        """Test unknown platform raises error"""
        with pytest.raises(PlatformNotSupportedError):
            price_service._get_provider(Platform.UNKNOWN)

    def test_provider_cached(self, price_service):
        """Test provider is cached and reused"""
        provider1 = price_service._get_provider(Platform.JD)
        provider2 = price_service._get_provider(Platform.JD)
        assert provider1 is provider2


class TestGetPrice:
    """Test get_price method"""

    @pytest.mark.asyncio
    async def test_get_price_jd_url(self, price_service):
        """Test getting price from JD URL"""
        # Mock JD API response
        api_response = MagicMock()
        api_response.status_code = 200
        api_response.json.return_value = [
            {"id": "J_123", "p": "2999.00", "op": "3299.00"}
        ]

        # Mock HTML response for name
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '<div class="sku-name">JD Product</div>'

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(
                side_effect=[api_response, html_response]
            )

            result = await price_service.get_price(
                "https://item.jd.com/123.html"
            )

            assert isinstance(result, PriceData)
            assert result.platform == "jd"
            assert result.current_price == 2999.0

    @pytest.mark.asyncio
    async def test_get_price_taobao_url(self, price_service):
        """Test getting price from Taobao URL"""
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '''
            {"title": "Taobao Product", "price": "199.00"}
        '''

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=html_response)

            result = await price_service.get_price(
                "https://item.taobao.com/item.htm?id=123456"
            )

            assert isinstance(result, PriceData)
            assert result.platform == "taobao"
            assert result.current_price == 199.0

    @pytest.mark.asyncio
    async def test_get_price_with_platform_hint(self, price_service):
        """Test getting price with explicit platform hint"""
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '{"title": "Test", "price": "299.00"}'

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=html_response)

            result = await price_service.get_price(
                "https://detail.tmall.com/item.htm?id=789",
                platform="tmall"
            )

            assert result.platform == "tmall"

    @pytest.mark.asyncio
    async def test_get_price_unknown_url(self, price_service):
        """Test error with unknown URL"""
        with pytest.raises(PlatformNotSupportedError) as exc_info:
            await price_service.get_price("https://unknown-shop.com/item/123")

        assert "Cannot detect platform" in str(exc_info.value)
        assert "京东, 淘宝, 天猫, 拼多多" in str(exc_info.value)


class TestPlatformStats:
    """Test platform statistics"""

    def test_get_platform_stats(self, price_service, mock_anti_crawler):
        """Test getting platform statistics"""
        # Record some stats
        mock_anti_crawler.record_success("jd")
        mock_anti_crawler.record_success("jd")
        mock_anti_crawler.record_failure("jd")

        stats = price_service.get_platform_stats()

        assert "jd" in stats
        assert stats["jd"]["total_requests"] == 3
        assert stats["jd"]["successful_requests"] == 2


class TestMultiplePlatforms:
    """Test handling multiple platforms"""

    @pytest.mark.asyncio
    async def test_different_providers_for_different_platforms(self, price_service):
        """Test that different platforms use different providers"""
        # Get providers for different platforms
        jd_provider = price_service._get_provider(Platform.JD)
        taobao_provider = price_service._get_provider(Platform.TAOBAO)

        assert jd_provider is not taobao_provider
        assert jd_provider.platform == Platform.JD
        assert taobao_provider.platform == Platform.TAOBAO


class TestErrorHandling:
    """Test error handling in price service"""

    @pytest.mark.asyncio
    async def test_network_error_propagated(self, price_service):
        """Test network errors are propagated"""
        from src.modules.gift.providers.base import NetworkError

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )

            with pytest.raises(NetworkError):
                await price_service.get_price(
                    "https://item.jd.com/123.html"
                )

    @pytest.mark.asyncio
    async def test_parse_error_propagated(self, price_service):
        """Test parse errors are propagated"""
        from src.modules.gift.providers.base import ParseError

        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = "<html>No price data</html>"

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=html_response)

            with pytest.raises(ParseError):
                await price_service.get_price(
                    "https://item.taobao.com/item.htm?id=123"
                )
