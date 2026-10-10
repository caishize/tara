"""
Unit tests for Taobao (淘宝) price provider (T011)
Tests price fetching, HTML parsing, and error handling.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.modules.gift.providers.taobao_provider import TaobaoPriceProvider
from src.modules.gift.providers.base import (
    PriceData,
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
def taobao_provider(mock_anti_crawler):
    """Create Taobao provider with mock anti-crawler"""
    return TaobaoPriceProvider(anti_crawler=mock_anti_crawler, timeout=5.0)


class TestTaobaoProviderBasic:
    """Basic Taobao provider tests"""

    def test_provider_platform(self, taobao_provider):
        """Test provider has correct platform"""
        assert taobao_provider.platform == Platform.TAOBAO

    def test_provider_supports_taobao_url(self, taobao_provider):
        """Test provider supports Taobao URLs"""
        assert taobao_provider.supports_url(
            "https://item.taobao.com/item.htm?id=123456789"
        )
        assert not taobao_provider.supports_url(
            "https://item.jd.com/100026691566.html"
        )

    def test_h5_url_template(self, taobao_provider):
        """Test H5 URL template is properly formatted"""
        h5_url = taobao_provider.H5_URL_TEMPLATE.format(product_id="123456")
        assert "h5.m.taobao.com" in h5_url
        assert "123456" in h5_url


class TestTaobaoPriceExtraction:
    """Test price extraction from HTML"""

    def test_extract_price_from_json_pattern(self, taobao_provider):
        """Test extracting price from JSON in page"""
        html = '''
        <script>
            window.pageData = {
                "itemPrice": {"price": "299.00"}
            };
        </script>
        '''
        price = taobao_provider._extract_price_from_html(html)
        assert price == 299.0

    def test_extract_price_from_price_text(self, taobao_provider):
        """Test extracting price from priceText field"""
        html = '''
        <script>
            var data = {"priceText": "¥199.99"};
        </script>
        '''
        price = taobao_provider._extract_price_from_html(html)
        assert price == 199.99

    def test_extract_price_from_promotion_price(self, taobao_provider):
        """Test extracting promotion price"""
        html = '''
        <script>
            {"promotionPrice": "88.50"}
        </script>
        '''
        price = taobao_provider._extract_price_from_html(html)
        assert price == 88.5

    def test_extract_price_from_data_attribute(self, taobao_provider):
        """Test extracting price from data-price attribute"""
        html = '<div data-price="159.00">商品</div>'
        price = taobao_provider._extract_price_from_html(html)
        assert price == 159.0

    def test_extract_price_from_css_class(self, taobao_provider):
        """Test extracting price from element with class"""
        html = '<span class="price">¥299.00</span>'
        price = taobao_provider._extract_price_from_html(html)
        assert price == 299.0

    def test_extract_price_no_price_found(self, taobao_provider):
        """Test None returned when no price found"""
        html = "<html><body>No price here</body></html>"
        price = taobao_provider._extract_price_from_html(html)
        assert price is None

    def test_extract_price_invalid_price_ignored(self, taobao_provider):
        """Test invalid (zero) price is ignored"""
        html = '''
        <script>
            {"price": "0", "promotionPrice": "99.00"}
        </script>
        '''
        price = taobao_provider._extract_price_from_html(html)
        assert price == 99.0


class TestTaobaoNameExtraction:
    """Test product name extraction from HTML"""

    def test_extract_name_from_json_title(self, taobao_provider):
        """Test extracting name from JSON title field"""
        html = '''
        <script>
            {"title": "Apple iPhone 15 Pro Max 256GB"}
        </script>
        '''
        name = taobao_provider._extract_name_from_html(html)
        assert "iPhone" in name

    def test_extract_name_from_item_title(self, taobao_provider):
        """Test extracting name from itemTitle field"""
        html = '''
        <script>
            {"itemTitle": "小米14 Ultra 旗舰手机"}
        </script>
        '''
        name = taobao_provider._extract_name_from_html(html)
        assert "小米" in name

    def test_extract_name_from_h1(self, taobao_provider):
        """Test extracting name from h1.title element"""
        html = '''
        <html>
            <h1 class="title">华为 Mate 60 Pro</h1>
        </html>
        '''
        name = taobao_provider._extract_name_from_html(html)
        assert "华为" in name

    def test_extract_name_from_page_title(self, taobao_provider):
        """Test extracting name from page title"""
        html = '''
        <html>
            <head><title>商品名称-淘宝网</title></head>
        </html>
        '''
        name = taobao_provider._extract_name_from_html(html)
        assert "商品名称" in name
        assert "淘宝网" not in name  # Should be cleaned

    def test_extract_name_truncation(self, taobao_provider):
        """Test name is truncated to 200 characters"""
        long_name = "A" * 300
        html = f'''
        <script>
            {{"title": "{long_name}"}}
        </script>
        '''
        name = taobao_provider._extract_name_from_html(html)
        assert len(name) == 200

    def test_extract_name_none_when_not_found(self, taobao_provider):
        """Test None returned when name not found"""
        html = "<html><body>No title</body></html>"
        name = taobao_provider._extract_name_from_html(html)
        assert name is None


class TestTaobaoParsePriceFull:
    """Test full parse_price method"""

    @pytest.mark.asyncio
    async def test_parse_price_success(self, taobao_provider):
        """Test successful price parsing"""
        html = '''
        <html>
            <script>
                {"title": "Test Product", "price": "199.00"}
            </script>
        </html>
        '''
        url = "https://item.taobao.com/item.htm?id=123456789"

        result = await taobao_provider.parse_price(html, url)

        assert isinstance(result, PriceData)
        assert result.product_id == "123456789"
        assert result.current_price == 199.0
        assert result.platform == "taobao"
        assert "Test Product" in result.product_name

    @pytest.mark.asyncio
    async def test_parse_price_fallback_name(self, taobao_provider):
        """Test fallback product name when extraction fails"""
        html = '<script>{"price": "99.00"}</script>'
        url = "https://item.taobao.com/item.htm?id=999888"

        result = await taobao_provider.parse_price(html, url)

        assert result.product_name == "淘宝商品 999888"

    @pytest.mark.asyncio
    async def test_parse_price_invalid_url(self, taobao_provider):
        """Test error with invalid URL"""
        with pytest.raises(ProductNotFoundError):
            await taobao_provider.parse_price("<html></html>", "https://invalid.com/")

    @pytest.mark.asyncio
    async def test_parse_price_no_price(self, taobao_provider):
        """Test error when price not found"""
        html = "<html><body>No price data</body></html>"
        url = "https://item.taobao.com/item.htm?id=123"

        with pytest.raises(ParseError):
            await taobao_provider.parse_price(html, url)


class TestTaobaoGetPrice:
    """Test full get_price flow"""

    @pytest.mark.asyncio
    async def test_get_price_success(self, taobao_provider):
        """Test successful price fetch"""
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '''
        <html>
            <script>
                {"title": "Test Product", "price": "299.00"}
            </script>
        </html>
        '''

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=html_response)

            result = await taobao_provider.get_price(
                "https://item.taobao.com/item.htm?id=123456"
            )

            assert isinstance(result, PriceData)
            assert result.product_id == "123456"
            assert result.current_price == 299.0

    @pytest.mark.asyncio
    async def test_get_price_uses_h5_url(self, taobao_provider):
        """Test that get_price uses H5 mobile URL"""
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '{"price": "99.00"}'

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_get = AsyncMock(return_value=html_response)
            mock_client.return_value.get = mock_get

            await taobao_provider.get_price(
                "https://item.taobao.com/item.htm?id=789"
            )

            # Verify H5 URL was called
            call_args = mock_get.call_args
            assert "h5.m.taobao.com" in str(call_args)

    @pytest.mark.asyncio
    async def test_get_price_invalid_url(self, taobao_provider):
        """Test error with invalid product URL"""
        with pytest.raises(ProductNotFoundError):
            await taobao_provider.get_price("https://invalid.com/product")

    @pytest.mark.asyncio
    async def test_get_price_blocked_platform(self, mock_anti_crawler, taobao_provider):
        """Test error when platform is blocked"""
        # Simulate platform block
        for _ in range(5):
            mock_anti_crawler.record_failure("taobao", is_rate_limited=True)

        with pytest.raises(PlatformBlockedError):
            await taobao_provider.get_price(
                "https://item.taobao.com/item.htm?id=123"
            )
