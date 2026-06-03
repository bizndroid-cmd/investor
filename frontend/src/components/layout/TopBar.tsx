import { RefreshCw, User } from "lucide-react";
import { useRefreshPortfolio } from "@/hooks/usePortfolio";
import { useSocketStore } from "@/stores/socketStore";

export function TopBar() {
  const { mutate: refresh, isPending } = useRefreshPortfolio();
  const isReconnecting = useSocketStore((s) => s.isReconnecting);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-4 md:px-6">
      <h1 className="text-lg font-semibold">Stock Dashboard</h1>

      <div className="flex items-center gap-3">
        {isReconnecting && (
          <span
            className="text-sm text-yellow-600 animate-pulse"
            role="status"
            aria-live="polite"
          >
            Reconnecting…
          </span>
        )}

        <button
          onClick={() => refresh()}
          disabled={isPending}
          aria-label="Refresh portfolio"
          className="inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${isPending ? "animate-spin" : ""}`} />
        </button>

        <button
          aria-label="User menu"
          className="inline-flex items-center justify-center rounded-full p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <User className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}
