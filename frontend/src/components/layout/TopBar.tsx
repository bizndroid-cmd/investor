import { RefreshCw, Sun, Moon, ChevronDown, LogOut } from "lucide-react";
import { useRefreshPortfolio } from "@/hooks/usePortfolio";
import { useSocketStore } from "@/stores/socketStore";
import { useActivePortfolio } from "@/contexts/PortfolioContext";
import { ForexBadge } from "@/components/common/ForexWidget";
import { useState, useEffect } from "react";

export function TopBar() {
  const { mutate: refresh, isPending } = useRefreshPortfolio();
  const isReconnecting = useSocketStore((s) => s.isReconnecting);
  const [isDark, setIsDark] = useState(() =>
    document.documentElement.classList.contains("dark")
  );

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDark]);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-card/90 backdrop-blur-xl px-4 md:px-6">
      <div className="flex items-center gap-3">
        <ForexBadge />
        <PortfolioSwitcher />
      </div>

      <div className="flex items-center gap-1.5">
        {isReconnecting && (
          <span
            className="text-xs text-warning animate-pulse-soft mr-2"
            role="status"
            aria-live="polite"
          >
            Reconnecting…
          </span>
        )}

        <button
          onClick={() => setIsDark(!isDark)}
          aria-label="Toggle theme"
          className="btn-icon"
        >
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <button
          onClick={() => refresh()}
          disabled={isPending}
          aria-label="Refresh portfolio"
          className="btn-icon"
        >
          <RefreshCw className={`h-4 w-4 ${isPending ? "animate-spin" : ""}`} />
        </button>

        <button
          onClick={() => {
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
            window.location.reload();
          }}
          aria-label="Logout"
          className="btn-icon text-muted-foreground hover:text-destructive"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}

function PortfolioSwitcher() {
  const { portfolios, activePortfolio, setActivePortfolio, isMultiPortfolio } = useActivePortfolio();
  const [open, setOpen] = useState(false);

  if (!isMultiPortfolio || !activePortfolio) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-secondary/50 text-xs font-medium hover:bg-secondary transition-colors"
      >
        <span className="text-muted-foreground">{activePortfolio.currency_symbol}</span>
        <span>{activePortfolio.name}</span>
        <ChevronDown className="h-3 w-3 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-48 rounded-lg border bg-card shadow-lg z-50 animate-fade-in">
          {portfolios.map((p) => (
            <button
              key={p.id}
              onClick={() => { setActivePortfolio(p.id); setOpen(false); window.location.reload(); }}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-secondary/50 transition-colors first:rounded-t-lg last:rounded-b-lg ${
                p.id === activePortfolio.id ? "bg-primary/10 text-primary font-medium" : ""
              }`}
            >
              <span className="mr-1.5">{p.currency_symbol}</span>
              {p.name}
              <span className="text-muted-foreground ml-1">({p.display_name})</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
