"""Scrapers module for trending gifts data fetching."""

from .base_scraper import BaseScraper, ScrapedGift
from .jd_scraper import JDScraper
from .smzdm_scraper import SMZDMScraper
from .web_search_scraper import WebSearchScraper

__all__ = [
    "BaseScraper",
    "ScrapedGift",
    "JDScraper",
    "SMZDMScraper",
    "WebSearchScraper",
]
