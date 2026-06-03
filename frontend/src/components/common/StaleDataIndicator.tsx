interface StaleDataIndicatorProps {
  lastUpdated: string;
}

export function StaleDataIndicator({ lastUpdated }: StaleDataIndicatorProps) {
  const date = new Date(lastUpdated);
  const now = new Date();
  // Ensure we never show a future timestamp
  const displayDate = date > now ? now : date;

  const timeAgo = getTimeAgo(displayDate, now);

  return (
    <span
      className="text-xs text-muted-foreground"
      aria-label={`Last updated ${timeAgo}`}
    >
      Updated {timeAgo}
    </span>
  );
}

function getTimeAgo(date: Date, now: Date): string {
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.max(0, Math.floor(diffMs / 1000));

  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return date.toLocaleDateString();
}
