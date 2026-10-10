"""
Unit tests for Pinduoduo (拼多多) price provider (T013)
Tests price fetching, HTML parsing, and error handling.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.modules.gift.providers.pdd_provider import PDDPriceProvider
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
def pdd_provider(mock_anti_crawler):
    """Create PDD provider with mock anti-crawler"""
    return PDDPriceProvider(anti_crawler=mock_anti_crawler, timeout=5.0)


class TestPDDProviderBasic:
    """Basic PDD provider tests"""

    def test_provider_platform(self, pdd_provider):
        """Test provider has correct platform"""
        assert pdd_provider.platform == Platform.PDD

    def test_provider_supports_pdd_urls(self, pdd_provider):
        """Test provider supports PDD URLs"""
        assert pdd_provider.supports_url(
            "https://mobile.yangkeduo.com/goods.html?goods_id=123456"
        )
        assert pdd_provider.supports_url(
            "https://www.pinduoduo.com/goods.html?goods_id=789"
        )
        assert not pdd_provider.supports_url(
            "https://item.jd.com/100026691566.html"
        )

    def test_mobile_url_template(self, pdd_provider):
        """Test mobile URL template is properly formatted"""
        url = pdd_provider.MOBILE_URL_TEMPLATE.format(product_id="123")
        assert "mobile.yangkeduo.com" in url
        assert "123" in url


class TestPDDPriceExtraction:
    """Test price extraction from HTML"""

    def test_extract_price_cents(self, pdd_provider):
        """Test extracting price in cents (分)"""
        html = '{"price": 19900}'  # 199.00 元
        price = pdd_provider._extract_price_from_html(html)
        assert price == 199.0

    def test_extract_min_group_price_cents(self, pdd_provider):
        """Test extracting minGroupPrice in cents"""
        html = '{"minGroupPrice": 9900}'  # 99.00 元
        price = pdd_provider._extract_price_from_html(html)
        assert price == 99.0

    def test_extract_min_normal_price(self, pdd_provider):
        """Test extracting minNormalPrice"""
        html = '{"minNormalPrice": 29900}'  # 299.00 元
        price = pdd_provider._extract_price_from_html(html)
        assert price == 299.0

    def test_extract_market_price(self, pdd_provider):
        """Test extracting marketPrice"""
        html = '{"marketPrice": 49900}'  # 499.00 元
        price = pdd_provider._extract_price_from_html(html)
        assert price == 499.0

    def test_extract_data_price_attribute(self, pdd_provider):
        """Test extracting from data-price attribute"""
        html = '<div data-price="8888">商品</div>'  # 88.88 元
        price = pdd_provider._extract_price_from_html(html)
        assert price == 88.88

    def test_extract_decimal_price(self, pdd_provider):
        """Test extracting decimal price format"""
        html = '{"price": "199.99"}'
        price = pdd_provider._extract_price_from_html(html)
        assert price == 199.99

    def test_extract_price_from_css_class(self, pdd_provider):
        """Test extracting price from element with price class"""
        html = '<span class="price">¥299.00</span>'
        price = pdd_provider._extract_price_from_html(html)
        assert price == 299.0

    def test_extract_price_none_when_not_found(self, pdd_provider):
        """Test None returned when no price found"""
        html = "<html><body>No price data</body></html>"
        price = pdd_provider._extract_price_from_html(html)
        assert price is None

    def test_extract_price_small_value_not_cents(self, pdd_provider):
        """Test small values (<=100) treated as yuan not cents"""
        html = '{"price": 99}'  # 99 元, not cents
        price = pdd_provider._extract_price_from_html(html)
        assert price == 99.0


class TestPDDNameExtraction:
    """Test product name extraction from HTML"""

    def test_extract_goods_name(self, pdd_provider):
        """Test extracting goodsName field"""
        html = '{"goodsName": "家用电器大促销特价商品"}'
        name = pdd_provider._extract_name_from_html(html)
        assert "家用电器" in name

    def test_extract_goods_name_snake_case(self, pdd_provider):
        """Test extracting goods_name field (snake_case)"""
        html = '{"goods_name": "手机配件数据线"}'
        name = pdd_provider._extract_name_from_html(html)
        assert "数据线" in name

    def test_extract_title(self, pdd_provider):
        """Test extracting title field"""
        html = '{"title": "运动鞋男女通用款"}'
        name = pdd_provider._extract_name_from_html(html)
        assert "运动鞋" in name

    def test_extract_name_from_goods_name_class(self, pdd_provider):
        """Test extracting from .goods-name element"""
        html = '<div class="goods-name">服装女装连衣裙</div>'
        name = pdd_provider._extract_name_from_html(html)
        assert "连衣裙" in name

    def test_extract_name_from_page_title(self, pdd_provider):
        """Test extracting and cleaning page title"""
        html = '''
        <html>
            <head><title>商品详情-拼多多购物</title></head>
        </html>
        '''
        name = pdd_provider._extract_name_from_html(html)
        assert "商品详情" in name
        assert "拼多多" not in name  # Should be cleaned

    def test_extract_name_truncation(self, pdd_provider):
        """Test name is truncated to 200 characters"""
        long_name = "C" * 300
        html = f'{{"goodsName": "{long_name}"}}'
        name = pdd_provider._extract_name_from_html(html)
        assert len(name) == 200

    def test_extract_name_none_when_not_found(self, pdd_provider):
        """Test None returned when name not found"""
        html = "<html><body>No title</body></html>"
        name = pdd_provider._extract_name_from_html(html)
        assert name is None


class TestPDDParsePriceFull:
    """Test full parse_price method"""

    @pytest.mark.asyncio
    async def test_parse_price_success(self, pdd_provider):
        """Test successful price parsing"""
        html = '{"goodsName": "测试商品", "price": 9999}'  # 99.99 元
        url = "https://mobile.yangkeduo.com/goods.html?goods_id=12345"

        result = await pdd_provider.parse_price(html, url)

        assert isinstance(result, PriceData)
        assert result.product_id == "12345"
        assert result.current_price == 99.99
        assert result.platform == "pdd"
        assert "测试商品" in result.product_name

    @pytest.mark.asyncio
    async def test_parse_price_with_fallback_name(self, pdd_provider):
        """Test fallback product name"""
        html = '{"price": 19900}'  # 199.00 元
        url = "https://mobile.yangkeduo.com/goods.html?goods_id=67890"

        result = await pdd_provider.parse_price(html, url)

        assert result.product_name == "拼多多商品 67890"

    @pytest.mark.asyncio
    async def test_parse_price_invalid_url(self, pdd_provider):
        """Test error with invalid URL"""
        with pytest.raises(ProductNotFoundError):
            await pdd_provider.parse_price("<html></html>", "https://invalid.com/")

    @pytest.mark.asyncio
    async def test_parse_price_no_price(self, pdd_provider):
        """Test error when price not found (JS rendering case)"""
        url = "https://mobile.yangkeduo.com/goods.html?goods_id=111"

        with pytest.raises(ParseError) as exc_info:
            await pdd_provider.parse_price("<html>No data</html>", url)

        assert "JS rendering" in str(exc_info.value)


class TestPDDGetPrice:
    """Test full get_price flow"""

    @pytest.mark.asyncio
    async def test_get_price_success(self, pdd_provider):
        """Test successful price fetch"""
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.text = '{"goodsName": "Test", "price": 29900}'

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=html_response)

            result = await pdd_provider.get_price(
                "https://mobile.yangkeduo.com/goods.html?goods_id=123"
            )

            assert isinstance(result, PriceData)
            assert result.current_price == 299.0

    @pytest.mark.asyncio
    async def test_get_price_invalid_url(self, pdd_provider):
        """Test error with invalid product URL (unrecognized domain)"""
        # Mock HTTP to avoid real network call; provider should still raise
        # ProductNotFoundError because product ID can't be extracted from URL
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Not a product page</html>"

        with patch.object(httpx.AsyncClient, '__aenter__') as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            with pytest.raises(ProductNotFoundError):
                await pdd_provider.get_price("https://invalid.com/product")


class TestPDDPriceConversion:
    """Test PDD-specific price conversion (cents to yuan)"""

    def test_large_cent_value_converted(self, pdd_provider):
        """Test values > 100 are converted from cents"""
        html = '{"minGroupPrice": 12345}'  # 123.45 元
        price = pdd_provider._extract_price_from_html(html)
        assert price == 123.45

    def test_100_cents_converted(self, pdd_provider):
        """Test exactly 100 cents is treated as 100 yuan"""
        html = '{"price": 100}'  # Could be 100 yuan or 1 yuan
        price = pdd_provider._extract_price_from_html(html)
        # 100 is <= 100, so treated as yuan
        assert price == 100.0

    def test_101_cents_converted(self, pdd_provider):
        """Test 101 cents is converted to 1.01 yuan"""
        html = '{"price": 101}'  # 1.01 yuan
        price = pdd_provider._extract_price_from_html(html)
        assert price == 1.01
