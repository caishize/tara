"""
Unit tests for JD (京东) price provider (T010)
Tests price fetching, API parsing, and error handling.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json

import httpx

from src.modules.gift.providers.jd_provider import JDPriceProvider
from src.modules.gift.providers.base import (
    PriceData,
    NetworkError,
    RateLimitedError,
    ParseError,
    ProductNotFoundError,
    PlatformBlockedError,
)
from src.modules.gift.providers.platform_detector import Platform
from src.modules.gift.providers.anti_crawler import AntiCrawlerManager, AntiCrawlerConfig


@pytest.fixture
def mock_anti_crawler():
    """Create mock anti-crawler manager that doesn't wait"""
    config = AntiCrawlerConfig(base_delay_min=0, base_delay_max=0.001)
    manager = AntiCrawlerManager(config)
    return manager


@pytest.fixture
def jd_provider(mock_anti_crawler):
    """Create JD provider with mock anti-crawler"""
    return JDPriceProvider(anti_crawler=mock_anti_crawler, timeout=5.0)


class TestJDProviderBasic:
    """Basic JD provider tests"""

    def test_provider_platform(self, jd_provider):
        """Test provider has correct platform"""
        assert jd_provider.platform == Platform.JD

    def test_provider_supports_jd_url(self, jd_provider):
        """Test provider supports JD URLs"""
        assert jd_provider.supports_url("https://item.jd.com/100026691566.html")
        assert not jd_provider.supports_url("https://item.taobao.com/item.htm?id=123")


class TestJDPriceAPIResponse:
    """Test JD price API response parsing"""

    @pytest.mark.asyncio
    async def test_fetch_price_from_api_success(self, jd_provider):
        """Test successful price API fetch"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "J_100026691566", "p": "2999.00", "m": "3299.00", "op": "3599.00"}
        ]

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            price, original_price = await jd_provider._fetch_price_from_api("100026691566")

            assert price == 2999.0
            assert original_price == 3599.0

    @pytest.mark.asyncio
    async def test_fetch_price_from_api_no_original_price(self, jd_provider):
        """Test API response without original price"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "J_100026691566", "p": "1999.00", "m": "1999.00"}
        ]

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            price, original_price = await jd_provider._fetch_price_from_api("100026691566")

            assert price == 1999.0
            assert original_price == 1999.0  # Falls back to m when op is absent

    @pytest.mark.asyncio
    async def test_fetch_price_from_api_empty_response(self, jd_provider):
        """Test empty API response raises ProductNotFoundError"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            with pytest.raises(ProductNotFoundError):
                await jd_provider._fetch_price_from_api("999999999")

    @pytest.mark.asyncio
    async def test_fetch_price_from_api_invalid_price(self, jd_provider):
        """Test invalid price raises ParseError"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "J_123", "p": "0", "m": "0"}
        ]

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            with pytest.raises(ParseError):
                await jd_provider._fetch_price_from_api("123")

    @pytest.mark.asyncio
    async def test_fetch_price_from_api_network_error(self, jd_provider):
        """Test network error handling"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            with pytest.raises(NetworkError):
                await jd_provider._fetch_price_from_api("123")

    @pytest.mark.asyncio
    async def test_fetch_price_from_api_timeout(self, jd_provider):
        """Test timeout error handling"""
        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )

            with pytest.raises(NetworkError) as exc_info:
                await jd_provider._fetch_price_from_api("123")

            assert "timeout" in str(exc_info.value).lower()


class TestJDProductNameFetch:
    """Test product name fetching from HTML"""

    @pytest.mark.asyncio
    async def test_fetch_product_name_success(self, jd_provider):
        """Test successful product name extraction"""
        html = '''
        <html>
            <head><title>Apple iPhone 15 Pro Max 256GB - 京东</title></head>
            <body>
                <div class="sku-name">Apple iPhone 15 Pro Max 256GB 天然钛</div>
            </body>
        </html>
        '''
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            name = await jd_provider._fetch_product_name(
                "https://item.jd.com/123.html", "123"
            )

            assert "iPhone" in name or "Apple" in name

    @pytest.mark.asyncio
    async def test_fetch_product_name_fallback(self, jd_provider):
        """Test fallback to default name on failure"""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            name = await jd_provider._fetch_product_name(
                "https://item.jd.com/123.html", "123"
            )

            assert name == "京东商品 123"


class TestJDHTMLParsing:
    """Test HTML price parsing (fallback method)"""

    @pytest.mark.asyncio
    async def test_parse_price_from_html(self, jd_provider):
        """Test price extraction from HTML"""
        html = '''
        <html>
            <body>
                <div class="sku-name">Test Product</div>
                <span class="p-price"><span>2999.00</span></span>
            </body>
        </html>
        '''

        result = await jd_provider.parse_price(html, "https://item.jd.com/123.html")

        assert result.product_id == "123"
        assert result.current_price == 2999.0
        assert result.product_name == "Test Product"
        assert result.platform == "jd"

    @pytest.mark.asyncio
    async def test_parse_price_missing_product_id(self, jd_provider):
        """Test error when product ID cannot be extracted"""
        with pytest.raises(ProductNotFoundError):
            await jd_provider.parse_price("<html></html>", "https://invalid.url/")

    @pytest.mark.asyncio
    async def test_parse_price_no_price_found(self, jd_provider):
        """Test error when price cannot be found in HTML"""
        html = '<html><body><div>No price here</div></body></html>'

        with pytest.raises(ParseError):
            await jd_provider.parse_price(html, "https://item.jd.com/123.html")


class TestJDGetPrice:
    """Test complete get_price flow"""

    @pytest.mark.asyncio
    async def test_get_price_success(self, jd_provider):
        """Test successful price fetch"""
        # Mock API response
        api_response = MagicMock()
        api_response.status_code = 200
        api_response.json.return_value = [
            {"id": "J_123", "p": "1999.00", "op": "2299.00"}
        ]

        # Mock HTML response for name
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '<div class="sku-name">Test Product</div>'

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            # Return different responses for API and HTML calls
            mock_client.return_value.get = AsyncMock(
                side_effect=[api_response, html_response]
            )

            result = await jd_provider.get_price("https://item.jd.com/123.html")

            assert isinstance(result, PriceData)
            assert result.product_id == "123"
            assert result.current_price == 1999.0
            assert result.original_price == 2299.0
            assert result.platform == "jd"

    @pytest.mark.asyncio
    async def test_get_price_invalid_url(self, jd_provider):
        """Test error with invalid product URL"""
        with pytest.raises(ProductNotFoundError):
            await jd_provider.get_price("https://invalid.com/product")

    @pytest.mark.asyncio
    async def test_get_price_blocked_platform(self, mock_anti_crawler, jd_provider):
        """Test error when platform is blocked"""
        # Simulate platform block
        for _ in range(5):
            mock_anti_crawler.record_failure("jd", is_rate_limited=True)

        with pytest.raises(PlatformBlockedError):
            await jd_provider.get_price("https://item.jd.com/123.html")


class TestDiscountCalculation:
    """Test discount percentage calculation"""

    def test_calculate_discount_with_drop(self, jd_provider):
        """Test discount calculation with price drop"""
        discount = jd_provider._calculate_discount(2999.0, 3999.0)
        assert discount is not None
        assert 20 < discount < 30  # ~25% discount

    def test_calculate_discount_no_drop(self, jd_provider):
        """Test no discount when price is same or higher"""
        assert jd_provider._calculate_discount(2999.0, 2999.0) is None
        assert jd_provider._calculate_discount(2999.0, 2500.0) is None

    def test_calculate_discount_no_original(self, jd_provider):
        """Test no discount when original price is None"""
        assert jd_provider._calculate_discount(2999.0, None) is None
