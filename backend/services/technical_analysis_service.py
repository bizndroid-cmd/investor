"""Technical Analysis Service — computes indicators from yfinance OHLCV data.

Indicators: SMA(20,50,200), RSI(14), MACD, Bollinger Bands, ATR(14), Support/Resistance.
Returns a unified dict for per-stock research cards.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _sma(prices: np.ndarray, period: int) -> float | None:
    """Simple moving average."""
    if len(prices) < period:
        return None
    return float(np.mean(prices[-period:]))


def _ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average (full array)."""
    if len(prices) < period:
        return np.array([])
    multiplier = 2 / (period + 1)
    ema = np.zeros(len(prices))
    ema[period - 1] = np.mean(prices[:period])
    for i in range(period, len(prices)):
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def _rsi(prices: np.ndarray, period: int = 14) -> float | None:
    """Relative Strength Index."""
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(float(100 - (100 / (1 + rs))), 2)


def _macd(prices: np.ndarray) -> dict | None:
    """MACD (12,26,9)."""
    if len(prices) < 26:
        return None
    ema12 = _ema(prices, 12)
    ema26 = _ema(prices, 26)
    macd_line = ema12 - ema26
    # Signal line: EMA(9) of MACD
    if len(macd_line) < 35:  # Need at least 26+9
        return None
    signal = _ema(macd_line[25:], 9)
    if len(signal) < 1:
        return None
    macd_val = float(macd_line[-1])
    signal_val = float(signal[-1])
    histogram = macd_val - signal_val
    return {
        "macd": round(macd_val, 2),
        "signal": round(signal_val, 2),
        "histogram": round(histogram, 2),
        "trend": "bullish" if histogram > 0 else "bearish",
    }


def _bollinger_bands(prices: np.ndarray, period: int = 20) -> dict | None:
    """Bollinger Bands (20, 2 std dev)."""
    if len(prices) < period:
        return None
    sma = float(np.mean(prices[-period:]))
    std = float(np.std(prices[-period:]))
    upper = sma + 2 * std
    lower = sma - 2 * std
    current = float(prices[-1])
    # Position within bands (0=lower, 1=upper)
    width = upper - lower
    position = (current - lower) / width if width > 0 else 0.5
    return {
        "upper": round(upper, 2),
        "middle": round(sma, 2),
        "lower": round(lower, 2),
        "width": round(width, 2),
        "position": round(position, 2),
        "signal": "overbought" if position > 0.8 else "oversold" if position < 0.2 else "neutral",
    }


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float | None:
    """Average True Range."""
    if len(closes) < period + 1:
        return None
    true_ranges = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return None
    return round(float(np.mean(true_ranges[-period:])), 2)


def _support_resistance(prices: np.ndarray, period: int = 30) -> dict:
    """Simple support/resistance from recent highs/lows."""
    recent = prices[-period:] if len(prices) >= period else prices
    if len(recent) < 5:
        return {"support": None, "resistance": None}

    # Support: recent lows cluster
    sorted_prices = np.sort(recent)
    support = float(np.percentile(sorted_prices, 10))
    resistance = float(np.percentile(sorted_prices, 90))

    return {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "current_vs_support_pct": round((float(prices[-1]) - support) / support * 100, 1) if support > 0 else None,
        "current_vs_resistance_pct": round((resistance - float(prices[-1])) / float(prices[-1]) * 100, 1) if prices[-1] > 0 else None,
    }


def _compute_technicals_sync(ticker: str, geo_id: str = "IN") -> dict[str, Any] | None:
    """Synchronous computation using yfinance download. Run in thread pool."""
    try:
        import yfinance
        from backend.geo.ticker_resolver import resolve

        yf_ticker = resolve(ticker, geo_id)
        stock = yfinance.Ticker(yf_ticker)
        df = stock.history(period="6mo")

        if df is None or df.empty or len(df) < 20:
            return None

        # Drop rows with NaN close prices (partial/today's incomplete data)
        df = df.dropna(subset=["Close"])
        if len(df) < 20:
            return None

        closes = df["Close"].values.astype(float)
        highs = df["High"].values.astype(float)
        lows = df["Low"].values.astype(float)
        volumes = df["Volume"].values.astype(float)

        current_price = float(closes[-1])
        prev_close = float(closes[-2]) if len(closes) >= 2 else current_price

        # Price change
        day_change = current_price - prev_close
        day_change_pct = (day_change / prev_close * 100) if prev_close > 0 else 0

        # Period returns
        week_return = ((current_price - float(closes[-5])) / float(closes[-5]) * 100) if len(closes) >= 5 else None
        month_return = ((current_price - float(closes[-22])) / float(closes[-22]) * 100) if len(closes) >= 22 else None
        three_month_return = ((current_price - float(closes[-66])) / float(closes[-66]) * 100) if len(closes) >= 66 else None

        # Moving averages
        sma20 = _sma(closes, 20)
        sma50 = _sma(closes, 50)
        sma200 = _sma(closes, 200)

        # Trend determination
        trend = "neutral"
        if sma20 and sma50:
            if current_price > sma20 > sma50:
                trend = "strong_bullish"
            elif current_price > sma20:
                trend = "bullish"
            elif current_price < sma20 < sma50:
                trend = "strong_bearish"
            elif current_price < sma20:
                trend = "bearish"

        # RSI
        rsi = _rsi(closes)

        # MACD
        macd = _macd(closes)

        # Bollinger Bands
        bollinger = _bollinger_bands(closes)

        # ATR
        atr = _atr(highs, lows, closes)

        # Support/Resistance
        sr = _support_resistance(closes)

        # Volume analysis
        avg_volume_20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else None
        current_volume = float(volumes[-1])
        volume_ratio = round(current_volume / avg_volume_20, 2) if avg_volume_20 and avg_volume_20 > 0 else None

        # 52-week high/low
        if len(closes) >= 252:
            high_52w = float(np.max(highs[-252:]))
            low_52w = float(np.min(lows[-252:]))
        else:
            high_52w = float(np.max(highs))
            low_52w = float(np.min(lows))

        from_52w_high_pct = round((current_price - high_52w) / high_52w * 100, 1)
        from_52w_low_pct = round((current_price - low_52w) / low_52w * 100, 1)

        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "day_change": round(day_change, 2),
            "day_change_pct": round(day_change_pct, 2),
            "returns": {
                "week": round(week_return, 2) if week_return else None,
                "month": round(month_return, 2) if month_return else None,
                "three_month": round(three_month_return, 2) if three_month_return else None,
            },
            "moving_averages": {
                "sma20": round(sma20, 2) if sma20 else None,
                "sma50": round(sma50, 2) if sma50 else None,
                "sma200": round(sma200, 2) if sma200 else None,
                "trend": trend,
            },
            "rsi": rsi,
            "rsi_signal": "overbought" if rsi and rsi > 70 else "oversold" if rsi and rsi < 30 else "neutral",
            "macd": macd,
            "bollinger": bollinger,
            "atr": atr,
            "support_resistance": sr,
            "volume": {
                "current": int(current_volume),
                "avg_20d": int(avg_volume_20) if avg_volume_20 else None,
                "ratio": volume_ratio,
                "signal": "high" if volume_ratio and volume_ratio > 1.5 else "low" if volume_ratio and volume_ratio < 0.5 else "normal",
            },
            "week_52": {
                "high": round(high_52w, 2),
                "low": round(low_52w, 2),
                "from_high_pct": from_52w_high_pct,
                "from_low_pct": from_52w_low_pct,
            },
        }

    except Exception as e:
        logger.warning("Technical analysis failed for %s: %s", ticker, str(e))
        return None


class TechnicalAnalysisService:
    """Async wrapper around technical analysis computations."""

    async def get_technicals(self, ticker: str, geo_id: str = "IN") -> dict[str, Any] | None:
        """Get all technical indicators for a ticker."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _compute_technicals_sync, ticker, geo_id)
