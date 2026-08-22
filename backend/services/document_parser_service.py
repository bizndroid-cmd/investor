"""AI-powered document parser — extracts portfolio/trade data from any broker format.

Supports: CSV, XLSX, PDF (text-based).
Uses LLM to understand column mappings regardless of broker format.
"""

from __future__ import annotations

import io
import json
import logging
from decimal import Decimal
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


async def parse_document(
    file_content: bytes,
    filename: str,
    broker: str,
    currency: str,
    doc_type: str = "holdings",  # holdings or orders
) -> dict[str, Any]:
    """Parse uploaded document using LLM to extract structured data.

    Returns:
    {
        "status": "success" | "partial" | "error",
        "columns": ["ticker", "quantity", "price", ...],
        "rows": [{...}, ...],
        "metadata": {"broker": ..., "account_name": ..., "date": ...},
        "raw_preview": "first 20 rows as text",
        "parse_log": ["Reading file...", "Detected 26 rows...", ...]
    }
    """
    parse_log = []

    # Step 1: Read file content
    parse_log.append(f"Reading {filename}...")
    text_content = await _extract_text(file_content, filename)

    if not text_content:
        return {"status": "error", "message": "Could not read file content", "parse_log": parse_log}

    parse_log.append(f"Extracted {len(text_content)} characters")
    parse_log.append(f"Broker: {broker} | Currency: {currency}")

    # Step 2: Truncate for LLM context
    # Keep first ~3000 chars (enough for headers + sample rows)
    truncated = text_content[:4000]
    parse_log.append(f"Preparing data for AI analysis...")

    # Step 3: Send to LLM for structured extraction
    parse_log.append("AI analyzing document structure...")

    prompt = f"""You are a financial document parser. Extract structured data from this broker document.

BROKER: {broker}
CURRENCY: {currency}
DOCUMENT TYPE: {doc_type}
FILENAME: {filename}

DOCUMENT CONTENT:
```
{truncated}
```

INSTRUCTIONS:
1. Identify the data table in the document (holdings, orders, or transactions).
2. Extract ALL rows of data.
3. Map columns to standardized names. Use these standard column names:
   - For holdings: ticker, stock_name, isin, quantity, avg_buy_price, buy_value, current_price, current_value, unrealized_pnl
   - For orders: ticker, stock_name, isin, trade_type (BUY/SELL), quantity, price, value, exchange, order_id, executed_at, status
4. Include metadata: account holder name, account number, statement date if visible.

RESPOND WITH VALID JSON ONLY (no markdown, no explanation):
{{
  "doc_type": "holdings" or "orders",
  "metadata": {{
    "account_name": "...",
    "account_number": "...",
    "statement_date": "YYYY-MM-DD or null",
    "total_invested": number or null,
    "total_value": number or null
  }},
  "columns": ["ticker", "stock_name", "quantity", ...],
  "rows": [
    {{"ticker": "RELIANCE", "stock_name": "Reliance Industries", "quantity": 2, ...}},
    ...
  ]
}}
"""

    try:
        from backend.dependencies import create_llm_service
        from langchain_core.messages import HumanMessage, SystemMessage

        llm_service = create_llm_service()
        llm = llm_service._get_llm()

        if llm is None:
            parse_log.append("LLM not configured — falling back to rule-based parsing")
            return await _fallback_parse(text_content, broker, currency, filename, parse_log)

        parse_log.append("Sending to AI model...")
        response = await llm.ainvoke([
            SystemMessage(content="You are a precise financial document parser. Output only valid JSON."),
            HumanMessage(content=prompt),
        ])

        parse_log.append("AI response received")
        parse_log.append("Parsing structured data...")

        # Parse LLM response
        response_text = response.content.strip()
        # Strip markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

        result = json.loads(response_text)

        rows = result.get("rows", [])
        columns = result.get("columns", [])
        metadata = result.get("metadata", {})

        parse_log.append(f"Extracted {len(rows)} records")
        parse_log.append(f"Columns: {', '.join(columns)}")

        if metadata.get("account_name"):
            parse_log.append(f"Account: {metadata['account_name']}")

        parse_log.append("✓ Parsing complete")

        return {
            "status": "success",
            "doc_type": result.get("doc_type", doc_type),
            "columns": columns,
            "rows": rows,
            "metadata": metadata,
            "parse_log": parse_log,
            "broker": broker,
            "currency": currency,
        }

    except json.JSONDecodeError as e:
        parse_log.append(f"AI response parsing failed: {str(e)[:100]}")
        parse_log.append("Falling back to rule-based parsing...")
        return await _fallback_parse(text_content, broker, currency, filename, parse_log)
    except Exception as e:
        parse_log.append(f"Error: {str(e)[:150]}")
        return {"status": "error", "message": str(e)[:200], "parse_log": parse_log}


async def _extract_text(content: bytes, filename: str) -> str | None:
    """Extract text from file based on extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "csv":
        return content.decode("utf-8", errors="replace")

    elif ext in ("xlsx", "xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            ws = wb.active
            lines = []
            for row in ws.iter_rows(values_only=True):
                line = "\t".join(str(cell) if cell is not None else "" for cell in row)
                lines.append(line)
            return "\n".join(lines)
        except Exception as e:
            logger.warning("XLSX parse error: %s", str(e))
            return None

    elif ext == "pdf":
        try:
            # Try basic text extraction
            import subprocess
            # Use pdftotext if available, else try PyPDF2-style
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(content))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
            except ImportError:
                pass

            # Fallback: decode as text (won't work for most PDFs)
            return content.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("PDF parse error: %s", str(e))
            return None

    # Try as plain text
    return content.decode("utf-8", errors="replace")


async def _fallback_parse(text: str, broker: str, currency: str, filename: str, parse_log: list) -> dict:
    """Rule-based fallback parser for common formats."""
    parse_log.append("Using rule-based parser...")

    lines = text.strip().split("\n")

    # Debug: log first 10 lines to understand format
    for i, line in enumerate(lines[:10]):
        parse_log.append(f"[L{i}] {line[:100]}")

    # Find header row — look for common keywords
    header_idx = None
    keywords = ["stock name", "ticker", "symbol", "name", "quantity", "isin", "security name", "description"]

    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        matches = sum(1 for kw in keywords if kw in line_lower)
        if matches >= 2:
            header_idx = i
            break

    if header_idx is None:
        parse_log.append("Could not detect header row")
        return {"status": "error", "message": "Could not find data table in document", "parse_log": parse_log}

    # Parse headers (handle leading/trailing whitespace and tabs)
    raw_headers = lines[header_idx].split("\t")
    headers = [h.strip() for h in raw_headers if h.strip()]
    parse_log.append(f"Headers ({len(headers)}): {', '.join(headers[:6])}...")

    # Standardize header names
    header_map = {}
    for h in headers:
        hl = h.lower()
        if "stock name" in hl or hl == "name":
            header_map[h] = "stock_name"
        elif hl == "isin":
            header_map[h] = "isin"
        elif "quantity" in hl or hl == "qty":
            header_map[h] = "quantity"
        elif "average" in hl or "avg" in hl and "price" in hl:
            header_map[h] = "avg_buy_price"
        elif "buy value" in hl or "invested" in hl:
            header_map[h] = "buy_value"
        elif "closing price" in hl or "current price" in hl:
            header_map[h] = "current_price"
        elif "closing value" in hl or "current value" in hl:
            header_map[h] = "current_value"
        elif "unrealised" in hl or "p&l" in hl or "pnl" in hl:
            header_map[h] = "unrealized_pnl"
        elif "symbol" in hl:
            header_map[h] = "ticker"
        elif "type" in hl:
            header_map[h] = "trade_type"
        elif "exchange" in hl and "order" not in hl:
            header_map[h] = "exchange"
        elif "execution" in hl or "date" in hl:
            header_map[h] = "executed_at"
        elif "value" in hl:
            header_map[h] = "value"
        elif "price" in hl:
            header_map[h] = "price"
        else:
            header_map[h] = h.lower().replace(" ", "_")

    standardized_headers = [header_map.get(h, h.lower().replace(" ", "_")) for h in headers]

    rows = []
    for line in lines[header_idx + 1:]:
        cells = line.split("\t")
        # Strip whitespace from cells
        cells = [c.strip() for c in cells]
        # Filter out empty rows — find cells matching header count
        non_empty = [c for c in cells if c]
        if len(non_empty) < 2:
            continue

        # Align cells with headers (handle leading empty tab)
        aligned_cells = [c.strip() for c in cells if c.strip()]
        if len(aligned_cells) < 2:
            continue

        row = {}
        for j, h in enumerate(standardized_headers):
            if j < len(aligned_cells):
                row[h] = aligned_cells[j]
        if row and any(v for v in row.values()):
            rows.append(row)

    # Generate ticker from stock_name if no ticker column
    if "ticker" not in standardized_headers and "stock_name" in standardized_headers:
        standardized_headers.insert(0, "ticker")
        for row in rows:
            # Use first word of stock name as rough ticker
            name = row.get("stock_name", "")
            row["ticker"] = name.split(" ")[0].upper() if name else ""

    parse_log.append(f"Extracted {len(rows)} rows")
    parse_log.append("✓ Fallback parsing complete")

    return {
        "status": "success" if rows else "error",
        "doc_type": "holdings",
        "columns": standardized_headers,
        "rows": rows,
        "metadata": {"broker": broker},
        "parse_log": parse_log,
        "broker": broker,
        "currency": currency,
        "message": None if rows else "No data rows found",
    }
