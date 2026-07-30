import { RefreshCw, User, Sun, Moon } from "lucide-react";
import { useRefreshPortfolio } from "@/hooks/usePortfolio";
import { useSocketStore } from "@/stores/socketStore";
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
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-card/80 backdrop-blur-md px-4 md:px-6">
      <h1 className="text-base font-semibold tracking-tight">Dashboard</h1>

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
          aria-label="User menu"
          className="btn-icon"
        >
          <User className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
