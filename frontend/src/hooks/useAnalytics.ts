/**
 * Lightweight analytics tracker — records page views, clicks, session duration.
 * Batches events and sends every 30s or on page unload.
 * Zero impact on UX — fire-and-forget, no blocking.
 */

import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

interface AnalyticsEvent {
  event_type: "page_view" | "click" | "session_end";
  page?: string;
  target?: string;
  duration_ms?: number;
  metadata?: Record<string, any>;
}

const eventQueue: AnalyticsEvent[] = [];
let sessionStart = Date.now();
let flushTimer: ReturnType<typeof setInterval> | null = null;

function flush() {
  if (eventQueue.length === 0) return;

  // Fire-and-forget POST
  const token = localStorage.getItem("access_token");
  if (!token) return;

  const events = eventQueue.splice(0, 50);
  const url = `${import.meta.env.VITE_API_URL || "/api"}/analytics/events`;
  const body = JSON.stringify({ events });

  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body,
    keepalive: true,
  }).catch(() => {});
}

function trackEvent(event: AnalyticsEvent) {
  eventQueue.push(event);
  if (eventQueue.length >= 10) flush();
}

export function trackClick(target: string, page?: string) {
  trackEvent({ event_type: "click", target, page: page || window.location.pathname });
}

/**
 * Hook: auto-tracks page views on route change + session duration on unload.
 * Place once in DashboardLayout.
 */
export function useAnalytics() {
  const location = useLocation();
  const pageStart = useRef(Date.now());

  // Track page view on route change
  useEffect(() => {
    const now = Date.now();
    const prevDuration = now - pageStart.current;

    // Record time spent on previous page
    if (prevDuration > 1000) {
      trackEvent({
        event_type: "page_view",
        page: location.pathname,
        duration_ms: prevDuration,
      });
    } else {
      trackEvent({ event_type: "page_view", page: location.pathname });
    }

    pageStart.current = now;
  }, [location.pathname]);

  // Flush timer + session end on unload
  useEffect(() => {
    sessionStart = Date.now();

    flushTimer = setInterval(flush, 30_000);

    const handleUnload = () => {
      trackEvent({
        event_type: "session_end",
        duration_ms: Date.now() - sessionStart,
      });
      flush();
    };

    window.addEventListener("beforeunload", handleUnload);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") flush();
    });

    return () => {
      if (flushTimer) clearInterval(flushTimer);
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, []);
}
