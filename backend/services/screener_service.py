"""Screener.in fundamentals scraper service.

Fetches key financial ratios, pros/cons, and quarterly data from screener.in
for Indian stocks. Data is cached in the database and refreshed monthly.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import StockFundamentals

logger = logging.getLogger(__name__)

SCREENER_BASE = "https://www.screener.in/company"


class ScreenerService:
    """Fetches and caches stock fundamentals from screener.in."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def fetch_and_store(self, ticker: str) -> dict | None:
        """Fetch fundamentals for a ticker and store in DB.

        Returns the parsed data dict, or None on failure.
        """
        data = await self._scrape_ticker(ticker)
        if not data:
            return None

        # Upsert into DB
        stmt = select(StockFundamentals).where(StockFundamentals.ticker == ticker)
        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.market_cap = data.get("market_cap")
            existing.current_price = data.get("current_price")
            existing.pe_ratio = data.get("pe_ratio")
            existing.book_value = data.get("book_value")
            existing.dividend_yield = data.get("dividend_yield")
            existing.roce = data.get("roce")
            existing.roe = data.get("roe")
            existing.face_value = data.get("face_value")
            existing.high_low = data.get("high_low")
            existing.pros = data.get("pros")
            existing.cons = data.get("cons")
            existing.fetched_at = datetime.now(timezone.utc)
        else:
            record = StockFundamentals(
                ticker=ticker,
                market_cap=data.get("market_cap"),
                current_price=data.get("current_price"),
                pe_ratio=data.get("pe_ratio"),
                book_value=data.get("book_value"),
                dividend_yield=data.get("dividend_yield"),
                roce=data.get("roce"),
                roe=data.get("roe"),
                face_value=data.get("face_value"),
                high_low=data.get("high_low"),
                pros=data.get("pros"),
                cons=data.get("cons"),
            )
            self._db.add(record)

        await self._db.commit()
        return data

    async def fetch_all_portfolio(self, tickers: list[str]) -> int:
        """Fetch fundamentals for all portfolio tickers. Returns count of successful fetches."""
        success_count = 0
        for ticker in tickers:
            try:
                # Check if we already have recent data (< 7 days old)
                stmt = select(StockFundamentals).where(StockFundamentals.ticker == ticker)
                result = await self._db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing and existing.fetched_at:
                    age = datetime.now(timezone.utc) - existing.fetched_at
                    if age < timedelta(days=7):
                        logger.debug("Skipping %s — data is %d days old", ticker, age.days)
                        success_count += 1
                        continue

                data = await self.fetch_and_store(ticker)
                if data:
                    success_count += 1
                    logger.debug("Fetched fundamentals for %s", ticker)

                # Rate limit: 2 seconds between requests to be polite
                await asyncio.sleep(2)

            except Exception as e:
                logger.warning("Failed to fetch %s: %s", ticker, str(e))

        logger.info("Screener fundamentals: %d/%d tickers updated", success_count, len(tickers))
        return success_count

    async def get_fundamentals(self, ticker: str) -> dict | None:
        """Get stored fundamentals for a ticker (from DB)."""
        stmt = select(StockFundamentals).where(StockFundamentals.ticker == ticker)
        result = await self._db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return None

        return {
            "ticker": record.ticker,
            "market_cap": record.market_cap,
            "current_price": record.current_price,
            "pe_ratio": record.pe_ratio,
            "book_value": record.book_value,
            "dividend_yield": record.dividend_yield,
            "roce": record.roce,
            "roe": record.roe,
            "face_value": record.face_value,
            "high_low": record.high_low,
            "pros": record.pros,
            "cons": record.cons,
            "fetched_at": record.fetched_at.isoformat() if record.fetched_at else None,
        }

    async def get_all_fundamentals(self, tickers: list[str]) -> list[dict]:
        """Get stored fundamentals for multiple tickers."""
        stmt = select(StockFundamentals).where(StockFundamentals.ticker.in_(tickers))
        result = await self._db.execute(stmt)
        records = result.scalars().all()

        return [
            {
                "ticker": r.ticker,
                "market_cap": r.market_cap,
                "pe_ratio": r.pe_ratio,
                "book_value": r.book_value,
                "dividend_yield": r.dividend_yield,
                "roce": r.roce,
                "roe": r.roe,
                "pros": r.pros,
                "cons": r.cons,
            }
            for r in records
        ]

    async def get_briefing_context(self, tickers: list[str]) -> str:
        """Get a formatted string of fundamentals for the LLM briefing prompt."""
        fundamentals = await self.get_all_fundamentals(tickers)
        if not fundamentals:
            return ""

        lines = ["Stock Fundamentals (from screener.in):"]
        for f in fundamentals:
            parts = [f"  {f['ticker']}:"]
            if f.get("pe_ratio"):
                parts.append(f"P/E={f['pe_ratio']}")
            if f.get("roce"):
                parts.append(f"ROCE={f['roce']}%")
            if f.get("roe"):
                parts.append(f"ROE={f['roe']}%")
            if f.get("dividend_yield"):
                parts.append(f"DivYield={f['dividend_yield']}%")
            if f.get("market_cap"):
                parts.append(f"MCap=₹{f['market_cap']}Cr")
            lines.append(" | ".join(parts))

            if f.get("pros"):
                lines.append(f"    Pros: {f['pros'][:150]}")
            if f.get("cons"):
                lines.append(f"    Cons: {f['cons'][:150]}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private scraping methods
    # ------------------------------------------------------------------

    async def _scrape_ticker(self, ticker: str) -> dict | None:
        """Scrape screener.in for a single ticker's fundamentals."""
        url = f"{SCREENER_BASE}/{ticker}/"

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                })

            if response.status_code != 200:
                logger.warning("Screener returned %d for %s", response.status_code, ticker)
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_page(soup, ticker)

        except Exception as e:
            logger.warning("Screener scrape failed for %s: %s", ticker, str(e))
            return None

    def _parse_page(self, soup: BeautifulSoup, ticker: str) -> dict:
        """Parse the screener.in company page."""
        data: dict = {"ticker": ticker}

        # Parse top ratios
        ul = soup.find("ul", id="top-ratios")
        if ul:
            for li in ul.find_all("li"):
                text = li.get_text(separator=" ", strip=True)
                self._extract_ratio(data, text)

        # Parse pros
        pros_div = soup.find("div", class_="pros")
        if pros_div:
            pros_list = [li.text.strip() for li in pros_div.find_all("li")]
            data["pros"] = " | ".join(pros_list[:4])

        # Parse cons
        cons_div = soup.find("div", class_="cons")
        if cons_div:
            cons_list = [li.text.strip() for li in cons_div.find_all("li")]
            data["cons"] = " | ".join(cons_list[:4])

        return data

    def _extract_ratio(self, data: dict, text: str) -> None:
        """Extract a ratio value from the text of a list item."""
        text_clean = re.sub(r"\s+", " ", text).strip()

        if "Market Cap" in text_clean:
            match = re.search(r"₹\s*([\d,]+)", text_clean)
            if match:
                data["market_cap"] = match.group(1).replace(",", "")

        elif "Current Price" in text_clean:
            match = re.search(r"₹\s*([\d,]+)", text_clean)
            if match:
                data["current_price"] = match.group(1).replace(",", "")

        elif "Stock P/E" in text_clean:
            match = re.search(r"([\d.]+)", text_clean.split("Stock P/E")[-1])
            if match:
                data["pe_ratio"] = match.group(1)

        elif "Book Value" in text_clean:
            match = re.search(r"₹\s*([\d,]+)", text_clean)
            if match:
                data["book_value"] = match.group(1).replace(",", "")

        elif "Dividend Yield" in text_clean:
            match = re.search(r"([\d.]+)\s*%", text_clean)
            if match:
                data["dividend_yield"] = match.group(1)

        elif "ROCE" in text_clean:
            match = re.search(r"([\d.]+)\s*%", text_clean)
            if match:
                data["roce"] = match.group(1)

        elif "ROE" in text_clean:
            match = re.search(r"([\d.]+)\s*%", text_clean)
            if match:
                data["roe"] = match.group(1)

        elif "Face Value" in text_clean:
            match = re.search(r"₹\s*([\d.]+)", text_clean)
            if match:
                data["face_value"] = match.group(1)

        elif "High / Low" in text_clean:
            match = re.search(r"₹\s*([\d,]+)\s*/\s*([\d,]+)", text_clean)
            if match:
                data["high_low"] = f"{match.group(1)}/{match.group(2)}"
