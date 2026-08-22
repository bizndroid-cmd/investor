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
    doc_type: str = "auto",
) -> dict[str, Any]:
    """Parse uploaded document — uses pandas for XLSX/CSV (reliable), LLM for PDF."""
    parse_log = []
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    parse_log.append(f"Reading {filename} ({ext})...")

    # For XLSX/CSV: use pandas directly (fast, reliable, no LLM needed)
    if ext in ("xlsx", "xls", "csv"):
        return await _parse_spreadsheet(file_content, filename, ext, broker, currency, doc_type, parse_log)

    # For PDF: extract text then use LLM or fallback
    text_content = await _extract_text(file_content, filename)
    if not text_content:
        return {"status": "error", "message": "Could not read file content", "parse_log": parse_log}

    parse_log.append(f"Extracted {len(text_content)} characters")
    return await _parse_with_fallback(text_content, broker, currency, doc_type, parse_log)


async def _parse_spreadsheet(
    content: bytes, filename: str, ext: str, broker: str, currency: str, doc_type: str, parse_log: list
) -> dict[str, Any]:
    """Parse XLSX/CSV using pandas — no LLM dependency."""
    try:
        import pandas as pd

        if ext == "csv":
            df = pd.read_csv(io.BytesIO(content))
        else:
            # Read all rows, find the actual header row
            df_raw = pd.read_excel(io.BytesIO(content), header=None)
            parse_log.append(f"Raw sheet: {df_raw.shape[0]} rows × {df_raw.shape[1]} columns")

            # Find header row: row with most non-null string values matching known keywords
            keywords = {"stock", "name", "isin", "quantity", "price", "value", "symbol",
                        "type", "exchange", "order", "date", "closing", "buy", "average"}
            header_idx = 0
            max_score = 0

            for i in range(min(15, len(df_raw))):
                row_vals = [str(v).lower() for v in df_raw.iloc[i] if pd.notna(v)]
                score = sum(1 for v in row_vals for kw in keywords if kw in v)
                if score > max_score:
                    max_score = score
                    header_idx = i

            parse_log.append(f"Header detected at row {header_idx}")

            # Re-read with correct header
            df = pd.read_excel(io.BytesIO(content), header=header_idx)

        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        # Drop completely empty rows
        df = df.dropna(how="all")
        # Drop rows where first meaningful column is NaN
        if len(df.columns) > 0:
            df = df.dropna(subset=[df.columns[0]])

        parse_log.append(f"Columns: {', '.join(df.columns[:8])}")
        parse_log.append(f"Data rows: {len(df)}")

        if len(df) == 0:
            return {"status": "error", "message": "No data rows found after header", "parse_log": parse_log}

        # Auto-detect doc_type
        col_lower = " ".join(df.columns).lower()
        if doc_type == "auto":
            if "execution" in col_lower or "order status" in col_lower or ("type" in col_lower and "buy" in df.to_string().lower()[:500]):
                doc_type = "orders"
            else:
                doc_type = "holdings"

        parse_log.append(f"Document type: {doc_type}")

        # Standardize column names
        col_map = {}
        for col in df.columns:
            cl = col.lower().strip()
            if cl in ("stock name", "stock_name", "security name"):
                col_map[col] = "stock_name"
            elif cl == "isin":
                col_map[col] = "isin"
            elif cl in ("quantity", "qty"):
                col_map[col] = "quantity"
            elif "average" in cl and "price" in cl:
                col_map[col] = "avg_buy_price"
            elif cl in ("buy value", "invested value"):
                col_map[col] = "buy_value"
            elif cl in ("closing price", "current price", "ltp"):
                col_map[col] = "current_price"
            elif cl in ("closing value", "current value", "market value"):
                col_map[col] = "current_value"
            elif "unrealised" in cl or "p&l" in cl or "pnl" in cl or "profit" in cl:
                col_map[col] = "unrealized_pnl"
            elif cl in ("symbol", "ticker"):
                col_map[col] = "ticker"
            elif cl == "type":
                col_map[col] = "trade_type"
            elif cl == "value":
                col_map[col] = "value"
            elif cl == "exchange":
                col_map[col] = "exchange"
            elif "execution" in cl or "date and time" in cl:
                col_map[col] = "executed_at"
            elif "order status" in cl or cl == "status":
                col_map[col] = "status"
            elif cl in ("exchange order id", "order id"):
                col_map[col] = "order_id"
            else:
                col_map[col] = cl.replace(" ", "_")

        df = df.rename(columns=col_map)

        # Add ticker from stock_name if missing
        if "ticker" not in df.columns and "stock_name" in df.columns:
            # For holdings without symbol, use first word of name
            df["ticker"] = df["stock_name"].apply(lambda x: str(x).split(" ")[0].upper() if pd.notna(x) else "")

        # Extract metadata
        metadata = {"broker": broker}
        if ext in ("xlsx", "xls"):
            # Try to read name/account from early rows
            df_meta = pd.read_excel(io.BytesIO(content), header=None, nrows=5)
            for i in range(min(5, len(df_meta))):
                row = [str(v) for v in df_meta.iloc[i] if pd.notna(v)]
                row_text = " ".join(row).lower()
                if "name" in row_text and len(row) >= 2:
                    metadata["account_name"] = row[-1] if row[-1].lower() != "name" else row[1] if len(row) > 1 else ""
                if "invested" in row_text:
                    for v in row:
                        try:
                            metadata["total_invested"] = float(v)
                        except (ValueError, TypeError):
                            pass

        # Convert to list of dicts
        rows = df.to_dict(orient="records")
        # Clean values for JSON serialization
        import numpy as np
        for row in rows:
            for k, v in list(row.items()):
                if v is None:
                    pass
                elif isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                    row[k] = None
                elif isinstance(v, float) and v == int(v):
                    row[k] = int(v)
                elif hasattr(v, "isoformat"):  # pandas Timestamp / datetime
                    row[k] = v.isoformat() if v is not pd.NaT else None
                elif isinstance(v, pd.Timestamp):
                    row[k] = str(v) if pd.notna(v) else None

        columns = list(df.columns)
        parse_log.append(f"✓ Extracted {len(rows)} records successfully")

        return {
            "status": "success",
            "doc_type": doc_type,
            "columns": columns,
            "rows": rows,
            "metadata": metadata,
            "parse_log": parse_log,
            "broker": broker,
            "currency": currency,
        }

    except Exception as e:
        parse_log.append(f"Spreadsheet parse error: {str(e)[:200]}")
        # Fall back to text extraction
        text = await _extract_text(content, filename)
        if text:
            return await _fallback_parse(text, broker, currency, filename, parse_log)
        return {"status": "error", "message": str(e)[:200], "parse_log": parse_log}


async def _parse_with_fallback(text: str, broker: str, currency: str, doc_type: str, parse_log: list) -> dict:
    """For non-spreadsheet files: try LLM, fall back to rule-based."""
    parse_log.append("Attempting AI parsing...")

    try:
        from backend.dependencies import create_llm_service
        from langchain_core.messages import HumanMessage, SystemMessage

        llm_service = create_llm_service()
        llm = llm_service._get_llm()

        if llm is None:
            raise ValueError("LLM not configured")

        truncated = text[:4000]
        prompt = f"""Extract structured financial data from this document. Broker: {broker}, Currency: {currency}.

DOCUMENT:
```
{truncated}
```

Return ONLY valid JSON:
{{"doc_type": "holdings" or "orders", "columns": [...], "rows": [{{...}}, ...], "metadata": {{}}}}"""

        response = await llm.ainvoke([
            SystemMessage(content="You are a financial document parser. Return only valid JSON."),
            HumanMessage(content=prompt),
        ])

        response_text = response.content.strip()
        if response_text.startswith("```"):
            response_text = "\n".join(response_text.split("\n")[1:])
            if response_text.endswith("```"):
                response_text = response_text[:-3]

        result = json.loads(response_text)
        rows = result.get("rows", [])
        parse_log.append(f"AI extracted {len(rows)} records")
        parse_log.append("✓ Parsing complete")

        return {
            "status": "success",
            "doc_type": result.get("doc_type", doc_type),
            "columns": result.get("columns", []),
            "rows": rows,
            "metadata": result.get("metadata", {}),
            "parse_log": parse_log,
            "broker": broker,
            "currency": currency,
        }
    except Exception as e:
        parse_log.append(f"AI parsing failed: {str(e)[:100]}")
        parse_log.append("Using rule-based fallback...")
        return await _fallback_parse(text, broker, currency, "", parse_log)


async def _extract_text(content: bytes, filename: str) -> str | None:
    """Extract text from file based on extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "csv":
        return content.decode("utf-8", errors="replace")

    elif ext in ("xlsx", "xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            lines = []
            for row in ws.iter_rows(values_only=True):
                line = "\t".join(str(cell) if cell is not None else "" for cell in row)
                lines.append(line)
            wb.close()
            return "\n".join(lines)
        except Exception as e:
            logger.warning("XLSX parse error: %s", str(e))
            return None

    elif ext == "pdf":
        try:
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(content))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
            except ImportError:
                pass
            return content.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("PDF parse error: %s", str(e))
            return None

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
