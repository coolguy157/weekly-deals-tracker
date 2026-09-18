"""
Weekly Deals Tracker & Price History Intelligence Engine.
"""

from .fetcher import FlippAdFetcher, FlyerItem, FlyerPage, FlyerMetadata
from .normalizer import ProductNormalizer, NormalizedDeal
from .database import DealsDatabase
from .analyzer import DealAnalyzer, DealEvaluation

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
]
