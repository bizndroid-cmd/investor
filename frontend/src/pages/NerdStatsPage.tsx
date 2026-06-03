import { useState, useEffect, useCallback } from "react";
import {
  verifyTelemetryPin,
  fetchTelemetryStats,
  fetchLLMCalls,
  fetchAPICalls,
  TelemetryStats,
  LLMCallLog,
  APICallLog,
} from "@/api/telemetry";

export function NerdStatsPage() {
  const [pin, setPin] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [pinError, setPinError] = useState(false);
  const [storedPin, setStoredPin] = useState("");

  const handlePinSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const valid = await verifyTelemetryPin(pin);
    if (valid) {
      setAuthenticated(true);
      setStoredPin(pin);
      setPinError(false);
    } else {
      setPinError(true);
    }
  };

  if (!authenticated) {
    return <PinGate pin={pin} setPin={setPin} onSubmit={handlePinSubmit} error={pinError} />;
  }

  return <StatsPanel pin={storedPin} />;
}

function PinGate({
  pin,
  setPin,
  onSubmit,
  error,
}: {
  pin: string;
  setPin: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  error: boolean;
}) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-xs rounded-lg border bg-card p-6 shadow-sm"
      >
        <h2 className="mb-1 text-lg font-semibold text-foreground">🤓 Nerd Stats</h2>
        <p className="mb-4 text-sm text-muted-foreground">Enter PIN to access system telemetry</p>
        <input
          type="password"
          maxLength={8}
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="Enter PIN"
          className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          autoFocus
        />
        {error && <p className="mt-2 text-xs text-red-500">Invalid PIN. Try again.</p>}
        <button
          type="submit"
          className="mt-4 w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Access
        </button>
      </form>
    </div>
  );
}

function StatsPanel({ pin }: { pin: string }) {
  const [stats, setStats] = useState<TelemetryStats | null>(null);
  const [llmCalls, setLLMCalls] = useState<LLMCallLog[]>([]);
  const [apiCalls, setAPICalls] = useState<APICallLog[]>([]);
  const [activeTab, setActiveTab] = useState<"overview" | "llm" | "api">("overview");
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [s, l, a] = await Promise.all([
        fetchTelemetryStats(pin),
        fetchLLMCalls(pin),
        fetchAPICalls(pin),
      ]);
      setStats(s);
      setLLMCalls(l);
      setAPICalls(a);
    } catch (err) {
      console.error("Failed to load telemetry:", err);
    } finally {
      setLoading(false);
    }
  }, [pin]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // refresh every 10s
    return () => clearInterval(interval);
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">Loading telemetry...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">🤓 Nerd Stats</h1>
        <button
          onClick={loadData}
          className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent"
        >
          Refresh
        </button>
      </div>

      {stats && <OverviewCards stats={stats} />}

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border p-1">
        {(["overview", "llm", "api"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              activeTab === tab
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent"
            }`}
          >
            {tab === "overview" ? "Overview" : tab === "llm" ? "LLM Calls" : "API Calls"}
          </button>
        ))}
      </div>

      {activeTab === "overview" && stats && <OverviewDetail stats={stats} />}
      {activeTab === "llm" && <LLMCallsTable calls={llmCalls} />}
      {activeTab === "api" && <APICallsTable calls={apiCalls} />}
    </div>
  );
}

function OverviewCards({ stats }: { stats: TelemetryStats }) {
  const uptime = formatUptime(stats.uptime_seconds);

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <StatCard label="Uptime" value={uptime} />
      <StatCard label="LLM Calls" value={String(stats.llm.total_calls)} />
      <StatCard label="Total Tokens" value={formatNumber(stats.llm.total_tokens)} />
      <StatCard label="API Calls" value={String(stats.api.total_calls)} />
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
    </div>
  );
}

function OverviewDetail({ stats }: { stats: TelemetryStats }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* LLM breakdown */}
      <div className="rounded-lg border p-4">
        <h3 className="mb-3 text-sm font-semibold">LLM Usage</h3>
        <div className="space-y-2 text-sm">
          <Row label="Successful" value={String(stats.llm.successful)} />
          <Row label="Failed" value={String(stats.llm.failed)} />
          <Row label="Prompt Tokens" value={formatNumber(stats.llm.total_prompt_tokens)} />
          <Row label="Completion Tokens" value={formatNumber(stats.llm.total_completion_tokens)} />
          <Row label="Avg Latency" value={`${stats.llm.avg_latency_ms}ms`} />
        </div>
        {Object.keys(stats.llm.by_provider).length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-medium text-muted-foreground mb-2">By Provider/Model</p>
            {Object.entries(stats.llm.by_provider).map(([key, val]) => (
              <div key={key} className="flex justify-between text-xs py-1 border-b last:border-0">
                <span className="font-mono">{key}</span>
                <span>{val.total} calls · {formatNumber(val.tokens)} tokens</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* API breakdown */}
      <div className="rounded-lg border p-4">
        <h3 className="mb-3 text-sm font-semibold">External API Usage</h3>
        <div className="space-y-2 text-sm">
          <Row label="Successful" value={String(stats.api.successful)} />
          <Row label="Failed" value={String(stats.api.failed)} />
          <Row label="Avg Latency" value={`${stats.api.avg_latency_ms}ms`} />
        </div>
        {Object.keys(stats.api.by_service).length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-medium text-muted-foreground mb-2">By Service</p>
            {Object.entries(stats.api.by_service).map(([key, val]) => (
              <div key={key} className="flex justify-between text-xs py-1 border-b last:border-0">
                <span className="font-mono">{key}</span>
                <span className="flex gap-2">
                  <span className="text-green-600">{val.success}✓</span>
                  {val.failed > 0 && <span className="text-red-500">{val.failed}✗</span>}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function LLMCallsTable({ calls }: { calls: LLMCallLog[] }) {
  if (calls.length === 0) {
    return <EmptyState message="No LLM calls recorded yet." />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/50">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Time</th>
            <th className="px-3 py-2 text-left font-medium">Provider</th>
            <th className="px-3 py-2 text-left font-medium">Purpose</th>
            <th className="px-3 py-2 text-right font-medium">Tokens</th>
            <th className="px-3 py-2 text-right font-medium">Latency</th>
            <th className="px-3 py-2 text-center font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {calls.map((call, i) => (
            <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
              <td className="px-3 py-2 font-mono text-xs">{formatTime(call.timestamp)}</td>
              <td className="px-3 py-2">
                <span className="font-mono text-xs">{call.provider}/{call.model}</span>
              </td>
              <td className="px-3 py-2">{call.purpose}</td>
              <td className="px-3 py-2 text-right font-mono">{call.total_tokens}</td>
              <td className="px-3 py-2 text-right font-mono">{call.latency_ms}ms</td>
              <td className="px-3 py-2 text-center">
                {call.success ? (
                  <span className="text-green-600">✓</span>
                ) : (
                  <span className="text-red-500" title={call.error || ""}>✗</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function APICallsTable({ calls }: { calls: APICallLog[] }) {
  if (calls.length === 0) {
    return <EmptyState message="No external API calls recorded yet." />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/50">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Time</th>
            <th className="px-3 py-2 text-left font-medium">Service</th>
            <th className="px-3 py-2 text-left font-medium">Endpoint</th>
            <th className="px-3 py-2 text-right font-medium">Status</th>
            <th className="px-3 py-2 text-right font-medium">Latency</th>
            <th className="px-3 py-2 text-center font-medium">OK</th>
          </tr>
        </thead>
        <tbody>
          {calls.map((call, i) => (
            <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
              <td className="px-3 py-2 font-mono text-xs">{formatTime(call.timestamp)}</td>
              <td className="px-3 py-2 font-medium">{call.service}</td>
              <td className="px-3 py-2 max-w-[200px] truncate font-mono text-xs" title={call.endpoint}>
                {call.method} {shortenUrl(call.endpoint)}
              </td>
              <td className="px-3 py-2 text-right font-mono">{call.status_code ?? "—"}</td>
              <td className="px-3 py-2 text-right font-mono">{call.latency_ms}ms</td>
              <td className="px-3 py-2 text-center">
                {call.success ? (
                  <span className="text-green-600">✓</span>
                ) : (
                  <span className="text-red-500" title={call.error || ""}>✗</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center rounded-lg border py-12">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-medium">{value}</span>
    </div>
  );
}

// Helpers
function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}

function shortenUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.pathname.slice(0, 30) + (u.pathname.length > 30 ? "..." : "");
  } catch {
    return url.slice(0, 30);
  }
}
