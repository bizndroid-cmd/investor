"""Offline Portfolio Import API — upload broker documents for AI parsing.

Endpoints:
- POST /imports/parse — upload document, returns parsed data
- POST /imports/confirm — confirm parsed data, populate across app
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.domain import Session
from backend.models.orm import PortfolioSnapshot, PortfolioDailySummary, TradeHistory, ETFHolding
from backend.routers.auth import get_current_user
from backend.dependencies import get_portfolio_id as get_portfolio_id_dep
from backend.services.document_parser_service import parse_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/parse")
async def parse_uploaded_document(
    file: UploadFile = File(...),
    broker: str = Form(...),
    currency: str = Form(...),
    doc_type: str = Form(default="auto"),
    session: Session = Depends(get_current_user),
) -> dict:
    """Upload and parse a broker document (CSV, XLSX, PDF).

    Returns structured data with columns + rows for user review.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Read file
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    # Detect doc_type from content if auto
    if doc_type == "auto":
        doc_type = "holdings"  # Default, LLM will figure it out

    # Parse using AI
    result = await parse_document(
        file_content=content,
        filename=file.filename,
        broker=broker,
        currency=currency,
        doc_type=doc_type,
    )

    return result


@router.post("/confirm")
async def confirm_import(
    body: dict,
    session: Session = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    portfolio_id=Depends(get_portfolio_id_dep),
) -> dict:
    """Confirm parsed data and populate across application.

    Body: {
        "doc_type": "holdings" or "orders",
        "broker": "groww",
        "currency": "INR",
        "rows": [...confirmed/edited rows...],
    }
    """
    doc_type = body.get("doc_type", "holdings")
    broker = body.get("broker", "unknown")
    currency = body.get("currency", "INR")
    rows = body.get("rows", [])

    if not rows:
        raise HTTPException(status_code=400, detail="No data to import")

    imported = 0
    today = date.today()

    if doc_type == "holdings":
        # Import as portfolio snapshot
        for row in rows:
            ticker = row.get("ticker") or row.get("symbol", "")
            if not ticker:
                continue

            quantity = Decimal(str(row.get("quantity", 0)))
            avg_price = Decimal(str(row.get("avg_buy_price") or row.get("buy_price") or row.get("average buy price") or 0))
            current_price = Decimal(str(row.get("current_price") or row.get("closing price") or row.get("closing_price") or avg_price))
            current_value = Decimal(str(row.get("current_value") or row.get("closing value") or row.get("closing_value") or 0))
            if current_value == 0 and current_price > 0:
                current_value = current_price * quantity
            invested = avg_price * quantity
            gain_loss = current_value - invested
            gain_loss_pct = (gain_loss / invested * 100) if invested > 0 else Decimal("0")

            snapshot = PortfolioSnapshot(
                id=uuid4(),
                user_id=session.user_id,
                portfolio_id=portfolio_id,
                snapshot_date=today,
                ticker=ticker.upper().replace(" ", ""),
                broker_id=broker,
                quantity=quantity,
                avg_buy_price=avg_price,
                current_price=current_price,
                current_value=current_value,
                gain_loss=gain_loss,
                gain_loss_percent=gain_loss_pct,
                currency=currency,
            )
            db.add(snapshot)
            imported += 1

        # Create daily summary
        total_value = sum(Decimal(str(r.get("current_value") or r.get("closing value") or r.get("closing_value") or 0)) for r in rows if r.get("ticker") or r.get("symbol"))
        total_invested = sum(
            Decimal(str(r.get("avg_buy_price") or r.get("buy_price") or r.get("average buy price") or 0)) * Decimal(str(r.get("quantity", 0)))
            for r in rows if r.get("ticker") or r.get("symbol")
        )
        total_gl = total_value - total_invested
        total_gl_pct = (total_gl / total_invested * 100) if total_invested > 0 else Decimal("0")

        summary = PortfolioDailySummary(
            id=uuid4(),
            user_id=session.user_id,
            portfolio_id=portfolio_id,
            snapshot_date=today,
            total_value=total_value,
            total_invested=total_invested,
            total_gain_loss=total_gl,
            total_gain_loss_percent=total_gl_pct,
            day_change=Decimal("0"),
            day_change_percent=Decimal("0"),
            holdings_count=imported,
        )
        db.add(summary)

    elif doc_type == "orders":
        # Import as trade history
        for row in rows:
            ticker = row.get("ticker") or row.get("symbol", "")
            if not ticker:
                continue

            trade_type = (row.get("trade_type") or row.get("type") or "BUY").upper()
            quantity = Decimal(str(row.get("quantity", 0)))
            price = Decimal(str(row.get("price") or row.get("value", 0)))
            if quantity > 0 and price > 0 and price > quantity:
                # price might be total value, compute per-unit
                price = price / quantity

            executed_at = None
            date_str = row.get("executed_at") or row.get("execution date and time") or row.get("date")
            if date_str:
                try:
                    from dateutil import parser as dateparser
                    executed_at = dateparser.parse(str(date_str))
                except Exception:
                    pass

            trade = TradeHistory(
                id=uuid4(),
                user_id=session.user_id,
                portfolio_id=portfolio_id,
                ticker=ticker.upper().replace(" ", ""),
                isin=row.get("isin"),
                trade_type=trade_type,
                quantity=quantity,
                price=price,
                value=Decimal(str(row.get("value", 0))) if row.get("value") else None,
                exchange=row.get("exchange"),
                order_id=row.get("order_id") or row.get("exchange order id"),
                executed_at=executed_at,
                broker=broker,
            )
            db.add(trade)
            imported += 1

    await db.commit()

    return {
        "status": "success",
        "imported": imported,
        "doc_type": doc_type,
        "broker": broker,
    }
