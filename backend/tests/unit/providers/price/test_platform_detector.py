"""
Unit tests for platform detector (T004)
Tests platform detection and product ID extraction for all supported e-commerce platforms.
"""
import pytest

from src.modules.gift.providers.platform_detector import (
    Platform,
    detect_platform,
    extract_product_id,
    detect_and_extract,
    is_supported_platform,
    get_platform_display_name,
)


class TestDetectPlatform:
    """Test platform detection from URL"""

    # JD (京东) URLs
    @pytest.mark.parametrize("url,expected", [
        ("https://item.jd.com/100026691566.html", Platform.JD),
        ("http://item.jd.com/12345.html", Platform.JD),
        ("https://item.m.jd.com/product/100026691566.html", Platform.JD),
        ("https://m.jd.com/product/12345.html", Platform.JD),
    ])
    def test_detect_jd_platform(self, url, expected):
        """Test JD URL detection (FR-005)"""
        assert detect_platform(url) == expected

    # Taobao (淘宝) URLs
    @pytest.mark.parametrize("url,expected", [
        ("https://item.taobao.com/item.htm?id=123456789", Platform.TAOBAO),
        ("https://h5.m.taobao.com/awp/core/detail.htm?id=123456", Platform.TAOBAO),
        ("https://a.m.taobao.com/i123456.htm", Platform.TAOBAO),
        ("https://detail.m.taobao.com/item.htm?id=789", Platform.TAOBAO),
    ])
    def test_detect_taobao_platform(self, url, expected):
        """Test Taobao URL detection (FR-005)"""
        assert detect_platform(url) == expected

    # Tmall (天猫) URLs
    @pytest.mark.parametrize("url,expected", [
        ("https://detail.tmall.com/item.htm?id=123456", Platform.TMALL),
        ("https://detail.m.tmall.com/item.htm?id=789", Platform.TMALL),
        ("https://chaoshi.detail.tmall.com/item.htm?id=456", Platform.TMALL),
    ])
    def test_detect_tmall_platform(self, url, expected):
        """Test Tmall URL detection (FR-005)"""
        assert detect_platform(url) == expected

    # PDD (拼多多) URLs
    @pytest.mark.parametrize("url,expected", [
        ("https://mobile.yangkeduo.com/goods.html?goods_id=123456", Platform.PDD),
        ("https://mobile.yangkeduo.com/goods123456.html", Platform.PDD),
        ("https://yangkeduo.com/goods.html?goods_id=789", Platform.PDD),
    ])
    def test_detect_pdd_platform(self, url, expected):
        """Test PDD URL detection (FR-005)"""
        assert detect_platform(url) == expected

    # Unknown/unsupported URLs
    @pytest.mark.parametrize("url", [
        "https://www.amazon.com/dp/B01234567",
        "https://www.ebay.com/itm/123456",
        "https://unknown.com/product/123",
        "",
        None,
    ])
    def test_detect_unknown_platform(self, url):
        """Test unknown platform detection returns UNKNOWN"""
        result = detect_platform(url) if url else Platform.UNKNOWN
        assert result == Platform.UNKNOWN


class TestExtractProductId:
    """Test product ID extraction from URL"""

    # JD product IDs
    @pytest.mark.parametrize("url,expected_id", [
        ("https://item.jd.com/100026691566.html", "100026691566"),
        ("https://item.jd.com/12345.html", "12345"),
        ("https://item.m.jd.com/product/999888.html", "999888"),
    ])
    def test_extract_jd_product_id(self, url, expected_id):
        """Test JD product ID extraction"""
        assert extract_product_id(url) == expected_id
        assert extract_product_id(url, Platform.JD) == expected_id

    # Taobao product IDs
    @pytest.mark.parametrize("url,expected_id", [
        ("https://item.taobao.com/item.htm?id=123456789", "123456789"),
        ("https://item.taobao.com/item.htm?spm=xxx&id=987654", "987654"),
        ("https://h5.m.taobao.com/awp/core/detail.htm?id=111222", "111222"),
    ])
    def test_extract_taobao_product_id(self, url, expected_id):
        """Test Taobao product ID extraction"""
        assert extract_product_id(url) == expected_id

    # Tmall product IDs
    @pytest.mark.parametrize("url,expected_id", [
        ("https://detail.tmall.com/item.htm?id=555666", "555666"),
        ("https://detail.tmall.com/item.htm?spm=abc&id=777888", "777888"),
    ])
    def test_extract_tmall_product_id(self, url, expected_id):
        """Test Tmall product ID extraction"""
        assert extract_product_id(url) == expected_id

    # PDD product IDs
    @pytest.mark.parametrize("url,expected_id", [
        ("https://mobile.yangkeduo.com/goods.html?goods_id=123456", "123456"),
        ("https://mobile.yangkeduo.com/goods.html?other=x&goods_id=789", "789"),
    ])
    def test_extract_pdd_product_id(self, url, expected_id):
        """Test PDD product ID extraction"""
        assert extract_product_id(url) == expected_id

    def test_extract_product_id_unknown_platform(self):
        """Test product ID extraction returns None for unknown platform"""
        assert extract_product_id("https://unknown.com/product/123") is None
        assert extract_product_id("") is None


class TestDetectAndExtract:
    """Test combined platform detection and ID extraction"""

    def test_detect_and_extract_jd(self):
        """Test combined detection and extraction for JD"""
        platform, product_id = detect_and_extract("https://item.jd.com/100026691566.html")
        assert platform == Platform.JD
        assert product_id == "100026691566"

    def test_detect_and_extract_taobao(self):
        """Test combined detection and extraction for Taobao"""
        platform, product_id = detect_and_extract("https://item.taobao.com/item.htm?id=123456")
        assert platform == Platform.TAOBAO
        assert product_id == "123456"

    def test_detect_and_extract_unknown(self):
        """Test combined detection returns None ID for unknown"""
        platform, product_id = detect_and_extract("https://unknown.com/product")
        assert platform == Platform.UNKNOWN
        assert product_id is None


class TestIsSupportedPlatform:
    """Test supported platform check"""

    @pytest.mark.parametrize("url,expected", [
        ("https://item.jd.com/123.html", True),
        ("https://item.taobao.com/item.htm?id=123", True),
        ("https://detail.tmall.com/item.htm?id=123", True),
        ("https://mobile.yangkeduo.com/goods.html?goods_id=123", True),
        ("https://www.amazon.com/dp/B123", False),
        ("https://unknown.com/product", False),
    ])
    def test_is_supported_platform(self, url, expected):
        """Test supported platform check"""
        assert is_supported_platform(url) == expected


class TestGetPlatformDisplayName:
    """Test platform display name"""

    @pytest.mark.parametrize("platform,expected_name", [
        (Platform.JD, "京东"),
        (Platform.TAOBAO, "淘宝"),
        (Platform.TMALL, "天猫"),
        (Platform.PDD, "拼多多"),
        (Platform.UNKNOWN, "未知平台"),
    ])
    def test_get_platform_display_name(self, platform, expected_name):
        """Test platform display name in Chinese"""
        assert get_platform_display_name(platform) == expected_name
