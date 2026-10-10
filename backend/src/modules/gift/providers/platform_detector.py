"""
Platform Detector
Detects e-commerce platform from product URL and extracts product ID
"""
import re
from typing import Optional, Tuple
from enum import Enum


class Platform(str, Enum):
    """Supported e-commerce platforms"""
    JD = "jd"
    TAOBAO = "taobao"
    TMALL = "tmall"
    PDD = "pdd"
    UNKNOWN = "unknown"


# URL patterns for each platform
PLATFORM_PATTERNS = {
    Platform.JD: [
        r"item\.jd\.com/(\d+)\.html",
        r"item\.m\.jd\.com/product/(\d+)\.html",
        r"m\.jd\.com/product/(\d+)\.html",
    ],
    Platform.TAOBAO: [
        r"item\.taobao\.com/item\.htm\?.*id=(\d+)",
        r"h5\.m\.taobao\.com/.*id=(\d+)",
        r"a\.m\.taobao\.com/i(\d+)\.htm",
        r"detail\.m\.taobao\.com/item\.htm\?.*id=(\d+)",
    ],
    Platform.TMALL: [
        r"detail\.tmall\.com/item\.htm\?.*id=(\d+)",
        r"detail\.m\.tmall\.com/item\.htm\?.*id=(\d+)",
        r"chaoshi\.detail\.tmall\.com/item\.htm\?.*id=(\d+)",
    ],
    Platform.PDD: [
        r"mobile\.yangkeduo\.com/goods\.html\?.*goods_id=(\d+)",
        r"mobile\.yangkeduo\.com/goods(\d+)\.html",
        r"yangkeduo\.com/goods\.html\?.*goods_id=(\d+)",
        r"(?:www\.)?pinduoduo\.com/goods\.html\?.*goods_id=(\d+)",
    ],
}

# Domain to platform mapping for quick lookup
DOMAIN_PLATFORM_MAP = {
    "item.jd.com": Platform.JD,
    "item.m.jd.com": Platform.JD,
    "m.jd.com": Platform.JD,
    "item.taobao.com": Platform.TAOBAO,
    "h5.m.taobao.com": Platform.TAOBAO,
    "a.m.taobao.com": Platform.TAOBAO,
    "detail.m.taobao.com": Platform.TAOBAO,
    "detail.tmall.com": Platform.TMALL,
    "detail.m.tmall.com": Platform.TMALL,
    "chaoshi.detail.tmall.com": Platform.TMALL,
    "mobile.yangkeduo.com": Platform.PDD,
    "yangkeduo.com": Platform.PDD,
    "www.pinduoduo.com": Platform.PDD,
    "pinduoduo.com": Platform.PDD,
}


def detect_platform(url: str) -> Platform:
    """
    Detect e-commerce platform from URL

    Args:
        url: Product page URL

    Returns:
        Platform enum value
    """
    if not url:
        return Platform.UNKNOWN

    url_lower = url.lower()

    # Quick domain-based detection
    for domain, platform in DOMAIN_PLATFORM_MAP.items():
        if domain in url_lower:
            return platform

    # Fallback to pattern matching
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform

    return Platform.UNKNOWN


def extract_product_id(url: str, platform: Optional[Platform] = None) -> Optional[str]:
    """
    Extract product ID from URL

    Args:
        url: Product page URL
        platform: Optional platform hint (auto-detect if None)

    Returns:
        Product ID string or None if not found
    """
    if not url:
        return None

    if platform is None:
        platform = detect_platform(url)

    if platform == Platform.UNKNOWN:
        return None

    patterns = PLATFORM_PATTERNS.get(platform, [])

    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def detect_and_extract(url: str) -> Tuple[Platform, Optional[str]]:
    """
    Detect platform and extract product ID in one call

    Args:
        url: Product page URL

    Returns:
        Tuple of (platform, product_id)
    """
    platform = detect_platform(url)
    product_id = extract_product_id(url, platform)
    return platform, product_id


def is_supported_platform(url: str) -> bool:
    """
    Check if URL is from a supported platform

    Args:
        url: Product page URL

    Returns:
        True if platform is supported
    """
    return detect_platform(url) != Platform.UNKNOWN


def get_platform_display_name(platform: Platform) -> str:
    """
    Get human-readable platform name

    Args:
        platform: Platform enum

    Returns:
        Display name in Chinese
    """
    names = {
        Platform.JD: "京东",
        Platform.TAOBAO: "淘宝",
        Platform.TMALL: "天猫",
        Platform.PDD: "拼多多",
        Platform.UNKNOWN: "未知平台",
    }
    return names.get(platform, "未知平台")
