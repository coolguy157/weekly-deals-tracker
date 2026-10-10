"""
SQLite storage engine for weekly circulars, product entities, and deal price history.
"""

from .db.connection import DealsDatabase

__all__ = ["DealsDatabase"]
