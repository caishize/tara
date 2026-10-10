"""
Unit tests for Tmall (天猫) price provider (T012)
Tests price fetching, HTML parsing, and error handling.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.modules.gift.providers.tmall_provider import TmallPriceProvider
from src.modules.gift.providers.base import (
    PriceData,
    ParseError,
    ProductNotFoundError,
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
def tmall_provider(mock_anti_crawler):
    """Create Tmall provider with mock anti-crawler"""
    return TmallPriceProvider(anti_crawler=mock_anti_crawler, timeout=5.0)


class TestTmallProviderBasic:
    """Basic Tmall provider tests"""

    def test_provider_platform(self, tmall_provider):
        """Test provider has correct platform"""
        assert tmall_provider.platform == Platform.TMALL

    def test_provider_supports_tmall_url(self, tmall_provider):
        """Test provider supports Tmall URLs"""
        assert tmall_provider.supports_url(
            "https://detail.tmall.com/item.htm?id=123456789"
        )
        assert not tmall_provider.supports_url(
            "https://item.jd.com/100026691566.html"
        )


class TestTmallPriceExtraction:
    """Test price extraction from HTML"""

    def test_extract_price_from_json(self, tmall_provider):
        """Test extracting price from JSON data"""
        html = '''
        <script>
            {"price": "599.00"}
        </script>
        '''
        price = tmall_provider._extract_price_from_html(html)
        assert price == 599.0

    def test_extract_default_item_price(self, tmall_provider):
        """Test extracting defaultItemPrice"""
        html = '''
        <script>
            {"defaultItemPrice": "1299.00"}
        </script>
        '''
        price = tmall_provider._extract_price_from_html(html)
        assert price == 1299.0

    def test_extract_price_info(self, tmall_provider):
        """Test extracting price from priceInfo object"""
        html = '''
        <script>
            {"priceInfo": {"price": "899.00", "type": "promotion"}}
        </script>
        '''
        price = tmall_provider._extract_price_from_html(html)
        assert price == 899.0

    def test_extract_data_price_attribute(self, tmall_provider):
        """Test extracting price from data-price attribute"""
        html = '<div class="item" data-price="459.00">商品</div>'
        price = tmall_provider._extract_price_from_html(html)
        assert price == 459.0

    def test_extract_tm_price_class(self, tmall_provider):
        """Test extracting price from tm-price element"""
        html = '<span class="tm-price">399.00</span>'
        price = tmall_provider._extract_price_from_html(html)
        assert price == 399.0

    def test_extract_tm_promo_price(self, tmall_provider):
        """Test extracting promotion price"""
        html = '<span class="tm-promo-price">¥199.00</span>'
        price = tmall_provider._extract_price_from_html(html)
        assert price == 199.0

    def test_extract_price_none_when_not_found(self, tmall_provider):
        """Test None returned when no price found"""
        html = "<html><body>No price</body></html>"
        price = tmall_provider._extract_price_from_html(html)
        assert price is None

    def test_extract_price_ignores_zero(self, tmall_provider):
        """Test zero price is ignored"""
        html = '''
        <script>
            {"price": "0", "defaultItemPrice": "299.00"}
        </script>
        '''
        price = tmall_provider._extract_price_from_html(html)
        assert price == 299.0


class TestTmallNameExtraction:
    """Test product name extraction from HTML"""

    def test_extract_name_from_title(self, tmall_provider):
        """Test extracting name from title field"""
        html = '''
        <script>
            {"title": "Apple MacBook Pro 14英寸"}
        </script>
        '''
        name = tmall_provider._extract_name_from_html(html)
        assert "MacBook" in name

    def test_extract_name_from_item_title(self, tmall_provider):
        """Test extracting name from itemTitle field"""
        html = '''
        <script>
            {"itemTitle": "Sony WH-1000XM5 降噪耳机"}
        </script>
        '''
        name = tmall_provider._extract_name_from_html(html)
        assert "Sony" in name

    def test_extract_name_from_h1(self, tmall_provider):
        """Test extracting name from h1 element"""
        html = '<html><h1>戴森吸尘器 V15</h1></html>'
        name = tmall_provider._extract_name_from_html(html)
        assert "戴森" in name

    def test_extract_name_from_page_title(self, tmall_provider):
        """Test extracting and cleaning page title"""
        html = '''
        <html>
            <head><title>商品名称-天猫Tmall.com</title></head>
        </html>
        '''
        name = tmall_provider._extract_name_from_html(html)
        assert "商品名称" in name
        assert "天猫" not in name  # Should be cleaned

    def test_extract_name_truncation(self, tmall_provider):
        """Test name is truncated to 200 characters"""
        long_name = "B" * 300
        html = f'{{"title": "{long_name}"}}'
        name = tmall_provider._extract_name_from_html(html)
        assert len(name) == 200

    def test_extract_name_none_when_short(self, tmall_provider):
        """Test short names (<=2 chars) are rejected"""
        html = '{"title": "AB"}'
        name = tmall_provider._extract_name_from_html(html)
        assert name is None

    def test_extract_name_none_when_not_found(self, tmall_provider):
        """Test None returned when name not found"""
        html = "<html><body>No title here</body></html>"
        name = tmall_provider._extract_name_from_html(html)
        assert name is None


class TestTmallParsePriceFull:
    """Test full parse_price method"""

    @pytest.mark.asyncio
    async def test_parse_price_success(self, tmall_provider):
        """Test successful price parsing"""
        html = '''
        <html>
            <script>{"title": "天猫商品", "price": "499.00"}</script>
        </html>
        '''
        url = "https://detail.tmall.com/item.htm?id=12345"

        result = await tmall_provider.parse_price(html, url)

        assert isinstance(result, PriceData)
        assert result.product_id == "12345"
        assert result.current_price == 499.0
        assert result.platform == "tmall"

    @pytest.mark.asyncio
    async def test_parse_price_with_fallback_name(self, tmall_provider):
        """Test fallback product name"""
        html = '<script>{"price": "199.00"}</script>'
        url = "https://detail.tmall.com/item.htm?id=67890"

        result = await tmall_provider.parse_price(html, url)

        assert result.product_name == "天猫商品 67890"

    @pytest.mark.asyncio
    async def test_parse_price_invalid_url(self, tmall_provider):
        """Test error with invalid URL"""
        with pytest.raises(ProductNotFoundError):
            await tmall_provider.parse_price("<html></html>", "https://invalid.com/")

    @pytest.mark.asyncio
    async def test_parse_price_no_price(self, tmall_provider):
        """Test error when price not found"""
        url = "https://detail.tmall.com/item.htm?id=111"

        with pytest.raises(ParseError):
            await tmall_provider.parse_price("<html>No price</html>", url)


class TestTmallGetPrice:
    """Test full get_price flow"""

    @pytest.mark.asyncio
    async def test_get_price_success(self, tmall_provider):
        """Test successful price fetch"""
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '{"title": "Test", "price": "599.00"}'

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=html_response)

            result = await tmall_provider.get_price(
                "https://detail.tmall.com/item.htm?id=123"
            )

            assert isinstance(result, PriceData)
            assert result.current_price == 599.0

    @pytest.mark.asyncio
    async def test_get_price_uses_correct_url(self, tmall_provider):
        """Test that get_price uses correct Tmall URL"""
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '{"price": "99.00"}'

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_get = AsyncMock(return_value=html_response)
            mock_client.return_value.get = mock_get

            await tmall_provider.get_price(
                "https://detail.tmall.com/item.htm?id=456"
            )

            # Verify tmall URL was called
            call_args = mock_get.call_args
            assert "tmall.com" in str(call_args) or "456" in str(call_args)

    @pytest.mark.asyncio
    async def test_get_price_invalid_url(self, tmall_provider):
        """Test error with invalid product URL (unrecognized domain)"""
        # Mock HTTP to avoid real network call; provider should still raise
        # ProductNotFoundError because product ID can't be extracted from URL
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Not a product page</html>"

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            with pytest.raises(ProductNotFoundError):
                await tmall_provider.get_price("https://invalid.com/product")
