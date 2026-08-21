/**
 * Market hours indicator — shows which markets are open/closed.
 * Highlights the rare overlap window when both are open.
 */
import { useState, useEffect } from "react";

interface MarketState {
  india: "open" | "closed" | "pre" | "post";
  us: "open" | "closed" | "pre" | "post";
  overlap: boolean;
}

function getMarketState(): MarketState {
  const now = new Date();

  // India: NSE 9:15 AM - 3:30 PM IST (UTC+5:30)
  const istOffset = 5.5 * 60; // minutes
  const istMinutes = (now.getUTCHours() * 60 + now.getUTCMinutes()) + istOffset;
  const istNormalized = ((istMinutes % 1440) + 1440) % 1440; // Handle day wrap
  const istDay = new Date(now.getTime() + istOffset * 60000).getUTCDay();

  let india: MarketState["india"] = "closed";
  if (istDay >= 1 && istDay <= 5) { // Mon-Fri
    if (istNormalized >= 555 && istNormalized < 930) india = "open"; // 9:15 - 15:30
    else if (istNormalized >= 540 && istNormalized < 555) india = "pre"; // 9:00 - 9:15
    else if (istNormalized >= 930 && istNormalized < 960) india = "post"; // 15:30 - 16:00
  }

  // US: NYSE 9:30 AM - 4:00 PM ET (UTC-4 summer, UTC-5 winter)
  // Simplified: assume ET = UTC-4 (EDT)
  const etOffset = -4 * 60;
  const etMinutes = (now.getUTCHours() * 60 + now.getUTCMinutes()) + etOffset;
  const etNormalized = ((etMinutes % 1440) + 1440) % 1440;
  const etDay = new Date(now.getTime() + etOffset * 60000).getUTCDay();

  let us: MarketState["us"] = "closed";
  if (etDay >= 1 && etDay <= 5) {
    if (etNormalized >= 570 && etNormalized < 960) us = "open"; // 9:30 - 16:00
    else if (etNormalized >= 540 && etNormalized < 570) us = "pre"; // 9:00 - 9:30
    else if (etNormalized >= 960 && etNormalized < 1020) us = "post"; // 16:00 - 17:00
  }

  return { india, us, overlap: india === "open" && us === "open" };
}

export function MarketStatusIndicator() {
  const [state, setState] = useState<MarketState>(getMarketState);

  useEffect(() => {
    const interval = setInterval(() => setState(getMarketState()), 60_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="hidden md:flex items-center gap-3 px-2.5 py-1 rounded-lg bg-secondary/30 text-[10px]">
      <MarketDot label="NSE" status={state.india} />
      <MarketDot label="NYSE" status={state.us} />
      {state.overlap && (
        <span className="text-amber-500 font-bold animate-pulse">BOTH LIVE</span>
      )}
    </div>
  );
}

function MarketDot({ label, status }: { label: string; status: string }) {
  const config = {
    open: { color: "bg-emerald-500", pulse: true, text: "text-emerald-500" },
    pre: { color: "bg-amber-500", pulse: true, text: "text-amber-500" },
    post: { color: "bg-amber-500", pulse: false, text: "text-amber-500" },
    closed: { color: "bg-muted-foreground/30", pulse: false, text: "text-muted-foreground" },
  }[status] || { color: "bg-muted-foreground/30", pulse: false, text: "text-muted-foreground" };

  return (
    <div className="flex items-center gap-1">
      <div className={`h-1.5 w-1.5 rounded-full ${config.color} ${config.pulse ? "animate-pulse" : ""}`} />
      <span className={`font-medium ${config.text}`}>{label}</span>
    </div>
  );
}
