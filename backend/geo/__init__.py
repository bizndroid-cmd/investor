"""Geography module — centralized registry of geography-specific configurations.

This module provides the foundation for multi-geography support.
All geography-dependent behavior flows from the configurations defined here.

Usage:
    from backend.geo.registry import get_geo, list_geos
    
    config = get_geo("IN")  # India
    config.currency_symbol  # "₹"
    config.yfinance_suffix  # ".NS"
"""
