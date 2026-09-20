"""
Weekly Deals Tracker & Price History Intelligence Engine.
"""

from .fetcher import FlippAdFetcher, FlyerItem, FlyerPage, FlyerMetadata
from .normalizer import ProductNormalizer, NormalizedDeal
from .database import DealsDatabase
from .analyzer import DealAnalyzer, DealEvaluation
from .formatter import format_badge, format_badge_fixed, print_deal_card

__all__ = [
    "FlippAdFetcher",
    "FlyerItem",
    "FlyerPage",
    "FlyerMetadata",
    "ProductNormalizer",
    "NormalizedDeal",
    "DealsDatabase",
    "DealAnalyzer",
    "DealEvaluation",
    "format_badge",
    "format_badge_fixed",
    "print_deal_card",
]
