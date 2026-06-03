"""Telemetry service for tracking LLM calls, API calls, tokens, and system stats.

Provides an in-memory store of usage metrics that resets on app restart.
Designed to give visibility into backend operations.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class LLMCall:
    """Record of a single LLM invocation."""
    timestamp: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    purpose: str  # e.g. "news_analysis", "portfolio_analysis"
    success: bool
    error: str | None = None


@dataclass
class APICall:
    """Record of an external API call (broker, market data, news, etc.)."""
    timestamp: str
    service: str  # e.g. "groww", "finnhub", "newsapi"
    endpoint: str
    method: str
    status_code: int | None
    latency_ms: float
    success: bool
    error: str | None = None


@dataclass
class TelemetryStats:
    """Aggregated telemetry statistics."""
    # LLM stats
    total_llm_calls: int = 0
    successful_llm_calls: int = 0
    failed_llm_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    avg_llm_latency_ms: float = 0.0

    # API stats
    total_api_calls: int = 0
    successful_api_calls: int = 0
    failed_api_calls: int = 0
    avg_api_latency_ms: float = 0.0

    # System
    uptime_seconds: float = 0.0
    started_at: str = ""


class TelemetryService:
    """In-memory telemetry tracker. Resets on app restart."""

    def __init__(self) -> None:
        self._llm_calls: list[LLMCall] = []
        self._api_calls: list[APICall] = []
        self._start_time = time.time()
        self._started_at = datetime.now(timezone.utc).isoformat()
        # Keep max 500 recent records of each
        self._max_records = 500
        # LLM status tracking
        self._last_llm_error: str | None = None
        self._last_llm_error_at: str | None = None
        self._rate_limited: bool = False
        self._rate_limit_retry_after: str | None = None  # ISO timestamp when to retry
        # Circuit breaker: block all LLM calls until this time
        self._circuit_open_until: float = 0.0  # unix timestamp

    def record_llm_call(
        self,
        *,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: float = 0.0,
        purpose: str = "unknown",
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Record an LLM call."""
        call = LLMCall(
            timestamp=datetime.now(timezone.utc).isoformat(),
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            purpose=purpose,
            success=success,
            error=error,
        )
        self._llm_calls.append(call)
        if len(self._llm_calls) > self._max_records:
            self._llm_calls = self._llm_calls[-self._max_records:]

        # Track rate limit state
        if not success and error:
            self._last_llm_error = error
            self._last_llm_error_at = call.timestamp
            error_lower = error.lower()
            if "429" in error or "rate" in error_lower or "quota" in error_lower or "resource_exhausted" in error_lower:
                self._rate_limited = True
                # Parse retry delay from error if possible
                cooldown_seconds = 300  # default 5 minutes
                retry_match = re.search(r'retry in (\d+(?:\.\d+)?)', error_lower)
                if retry_match:
                    parsed_delay = float(retry_match.group(1))
                    # Use at least 60s, at most 10 minutes
                    cooldown_seconds = max(60, min(parsed_delay * 2, 600))
                # If daily quota exhausted (limit: 0), use longer cooldown
                if "limit: 0" in error:
                    cooldown_seconds = 600  # 10 minutes — daily quota gone

                self._circuit_open_until = time.time() + cooldown_seconds
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
                self._rate_limit_retry_after = retry_at.isoformat()
        elif success:
            # Clear rate limit flag on success
            self._rate_limited = False
            self._rate_limit_retry_after = None
            self._circuit_open_until = 0.0

    def is_circuit_open(self) -> bool:
        """Check if the LLM circuit breaker is open (calls should be blocked).
        
        Returns True if we're in a cooldown period after rate limiting.
        """
        if self._circuit_open_until <= 0:
            return False
        if time.time() >= self._circuit_open_until:
            # Cooldown expired — close circuit
            self._circuit_open_until = 0.0
            self._rate_limited = False
            self._rate_limit_retry_after = None
            return False
        return True

    def get_circuit_remaining_seconds(self) -> float:
        """Get seconds remaining until circuit breaker closes."""
        if not self.is_circuit_open():
            return 0.0
        return max(0.0, self._circuit_open_until - time.time())

    def record_api_call(
        self,
        *,
        service: str,
        endpoint: str,
        method: str = "GET",
        status_code: int | None = None,
        latency_ms: float = 0.0,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Record an external API call."""
        call = APICall(
            timestamp=datetime.now(timezone.utc).isoformat(),
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )
        self._api_calls.append(call)
        if len(self._api_calls) > self._max_records:
            self._api_calls = self._api_calls[-self._max_records:]

    def get_stats(self) -> dict[str, Any]:
        """Get aggregated telemetry stats."""
        uptime = time.time() - self._start_time

        # LLM stats
        successful_llm = [c for c in self._llm_calls if c.success]
        failed_llm = [c for c in self._llm_calls if not c.success]
        total_prompt = sum(c.prompt_tokens for c in self._llm_calls)
        total_completion = sum(c.completion_tokens for c in self._llm_calls)
        total_tokens = sum(c.total_tokens for c in self._llm_calls)
        avg_llm_latency = (
            sum(c.latency_ms for c in self._llm_calls) / len(self._llm_calls)
            if self._llm_calls else 0.0
        )

        # API stats
        successful_api = [c for c in self._api_calls if c.success]
        failed_api = [c for c in self._api_calls if not c.success]
        avg_api_latency = (
            sum(c.latency_ms for c in self._api_calls) / len(self._api_calls)
            if self._api_calls else 0.0
        )

        # Per-service breakdown
        api_by_service: dict[str, dict] = {}
        for call in self._api_calls:
            if call.service not in api_by_service:
                api_by_service[call.service] = {"total": 0, "success": 0, "failed": 0}
            api_by_service[call.service]["total"] += 1
            if call.success:
                api_by_service[call.service]["success"] += 1
            else:
                api_by_service[call.service]["failed"] += 1

        # Per-provider LLM breakdown
        llm_by_provider: dict[str, dict] = {}
        for call in self._llm_calls:
            key = f"{call.provider}/{call.model}"
            if key not in llm_by_provider:
                llm_by_provider[key] = {"total": 0, "tokens": 0, "success": 0, "failed": 0}
            llm_by_provider[key]["total"] += 1
            llm_by_provider[key]["tokens"] += call.total_tokens
            if call.success:
                llm_by_provider[key]["success"] += 1
            else:
                llm_by_provider[key]["failed"] += 1

        return {
            "uptime_seconds": round(uptime, 1),
            "started_at": self._started_at,
            "llm": {
                "total_calls": len(self._llm_calls),
                "successful": len(successful_llm),
                "failed": len(failed_llm),
                "total_prompt_tokens": total_prompt,
                "total_completion_tokens": total_completion,
                "total_tokens": total_tokens,
                "avg_latency_ms": round(avg_llm_latency, 1),
                "by_provider": llm_by_provider,
            },
            "api": {
                "total_calls": len(self._api_calls),
                "successful": len(successful_api),
                "failed": len(failed_api),
                "avg_latency_ms": round(avg_api_latency, 1),
                "by_service": api_by_service,
            },
        }

    def get_llm_status(self) -> dict[str, Any]:
        """Get current LLM operational status for frontend consumption."""
        from backend.config import settings

        now = datetime.now(timezone.utc)

        # Check if circuit breaker has expired
        circuit_open = self.is_circuit_open()
        circuit_remaining = self.get_circuit_remaining_seconds()

        # Determine overall status
        if settings.llm_provider == "stub":
            status = "disabled"
            message = "LLM is in stub mode. No AI analysis available."
        elif circuit_open:
            status = "rate_limited"
            message = (
                f"AI analysis paused — cooldown active ({int(circuit_remaining)}s remaining). "
                f"Using free tier of {settings.llm_provider}/{getattr(settings, f'{settings.llm_provider}_model', 'unknown')}. "
                f"Will resume automatically when cooldown expires."
            )
        elif self._rate_limited:
            status = "rate_limited"
            message = (
                f"AI analysis temporarily paused due to API rate limits. "
                f"Using free tier of {settings.llm_provider}/{getattr(settings, f'{settings.llm_provider}_model', 'unknown')}. "
                f"Service will resume automatically."
            )
        elif self._last_llm_error and not any(c.success for c in self._llm_calls[-3:]):
            status = "error"
            message = f"AI service is experiencing issues. Last error: {self._last_llm_error[:100]}"
        else:
            status = "operational"
            message = f"AI analysis powered by {settings.llm_provider}/{getattr(settings, f'{settings.llm_provider}_model', 'unknown')}"

        # Usage info
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        recent_calls = [c for c in self._llm_calls if c.timestamp > one_hour_ago]
        calls_last_hour = len(recent_calls)

        return {
            "status": status,
            "message": message,
            "provider": settings.llm_provider,
            "model": getattr(settings, f"{settings.llm_provider}_model", "unknown") if settings.llm_provider != "stub" else None,
            "rate_limited": self._rate_limited or circuit_open,
            "retry_after": self._rate_limit_retry_after,
            "cooldown_remaining_seconds": int(circuit_remaining) if circuit_open else 0,
            "last_error": self._last_llm_error,
            "last_error_at": self._last_llm_error_at,
            "calls_last_hour": calls_last_hour,
            "total_calls_today": len(self._llm_calls),
            "limits_info": {
                "note": "Free tier limits apply. Circuit breaker pauses calls for 5-10 min on rate limit.",
                "rpm": 15,
                "rpd": 1000,
                "tpm": 250000,
            } if settings.llm_provider != "stub" else None,
        }

    def get_recent_llm_calls(self, limit: int = 50) -> list[dict]:
        """Get recent LLM call logs."""
        calls = self._llm_calls[-limit:]
        calls.reverse()
        return [
            {
                "timestamp": c.timestamp,
                "provider": c.provider,
                "model": c.model,
                "prompt_tokens": c.prompt_tokens,
                "completion_tokens": c.completion_tokens,
                "total_tokens": c.total_tokens,
                "latency_ms": round(c.latency_ms, 1),
                "purpose": c.purpose,
                "success": c.success,
                "error": c.error,
            }
            for c in calls
        ]

    def get_recent_api_calls(self, limit: int = 50) -> list[dict]:
        """Get recent API call logs."""
        calls = self._api_calls[-limit:]
        calls.reverse()
        return [
            {
                "timestamp": c.timestamp,
                "service": c.service,
                "endpoint": c.endpoint,
                "method": c.method,
                "status_code": c.status_code,
                "latency_ms": round(c.latency_ms, 1),
                "success": c.success,
                "error": c.error,
            }
            for c in calls
        ]


# Singleton instance
_telemetry: TelemetryService | None = None


def get_telemetry_service() -> TelemetryService:
    """Get or create the global telemetry service singleton."""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryService()
    return _telemetry


def reset_telemetry_service() -> None:
    """Reset telemetry (used on app restart)."""
    global _telemetry
    _telemetry = TelemetryService()
