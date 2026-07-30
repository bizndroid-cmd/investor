import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { useAlerts, useDeleteAlert, useCreateAlert } from "@/hooks/useAlerts";
import { showToast } from "@/components/common/Toast";
import {
  Bell, BellRing, Trash2, Plus, Send, CheckCircle2,
  TrendingUp, TrendingDown, Shield, Zap, Sparkles,
} from "lucide-react";

interface TelegramStatus {
  configured: boolean;
  chat_ids_count: number;
  active: boolean;
}

async function getTelegramStatus(): Promise<TelegramStatus> {
  return apiFetch("/alerts/telegram-status");
}

async function testTelegram(): Promise<{ success: boolean; message: string }> {
  return apiFetch("/alerts/telegram-test", { method: "POST" });
}

export function AlertsPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Bell className="h-6 w-6 text-amber-500" />
          Price Alerts
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Set price targets on your stocks. Get notified via Telegram when they hit.
        </p>
      </div>

      <TelegramConnectionCard />
      <ProximityCard />
      <SmartSuggestions />
      <CreateAlertCard />
      <ActiveAlerts />
      <TriggeredHistory />
    </div>
  );
}

// ============================================================
// TELEGRAM CONNECTION STATUS
// ============================================================
function TelegramConnectionCard() {
  const { data: status, isLoading } = useQuery({
    queryKey: ["telegram-status"],
    queryFn: getTelegramStatus,
  });

  const testMutation = useMutation({
    mutationFn: testTelegram,
    onSuccess: (data) => {
      showToast({
        title: data.success ? "Test sent!" : "Failed",
        variant: data.success ? "success" : "error",
      });
    },
  });

  if (isLoading) return <div className="bento-card h-20 skeleton-shimmer" />;

  const isActive = status?.active;

  return (
    <div className={`bento-card flex items-center justify-between ${isActive ? "border-emerald-500/20" : "border-amber-500/20"}`}>
      <div className="flex items-center gap-3">
        <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${isActive ? "bg-emerald-500/10" : "bg-amber-500/10"}`}>
          <Send className={`h-5 w-5 ${isActive ? "text-emerald-500" : "text-amber-500"}`} />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold">Telegram Notifications</p>
            {isActive ? (
              <span className="badge badge-success">Connected</span>
            ) : (
              <span className="badge badge-warning">Not Active</span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {isActive
              ? `Alerts delivered to ${status?.chat_ids_count} chat(s)`
              : "Configure TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS in .env"
            }
          </p>
        </div>
      </div>

      {isActive && (
        <button
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending}
          className="btn-ghost text-xs"
        >
          {testMutation.isPending ? "Sending..." : "Send Test"}
        </button>
      )}
    </div>
  );
}

// ============================================================
// PROXIMITY — how close are alerts to triggering
// ============================================================
function ProximityCard() {
  const { data: proximity, isLoading } = useQuery({
    queryKey: ["alert-proximity"],
    queryFn: () => apiFetch<any[]>("/alerts/proximity"),
    staleTime: 60_000,
  });

  if (isLoading) return <div className="bento-card h-16 skeleton-shimmer" />;
  if (!proximity || proximity.length === 0) return null;

  const imminent = proximity.filter((p: any) => p.status === "imminent");
  const close = proximity.filter((p: any) => p.status === "close");

  if (imminent.length === 0 && close.length === 0) return null;

  return (
    <div className="bento-card border-amber-500/20">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-3">
        <Zap className="h-4 w-4 text-amber-500" />
        Alerts Approaching Target
      </h3>
      <div className="space-y-2">
        {[...imminent, ...close].slice(0, 5).map((p: any) => (
          <div
            key={p.alert_id}
            className={`flex items-center justify-between p-3 rounded-lg border ${
              p.status === "imminent" ? "bg-red-500/5 border-red-500/20" : "bg-amber-500/5 border-amber-500/20"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`h-2 w-2 rounded-full ${p.status === "imminent" ? "bg-red-500 animate-pulse-soft" : "bg-amber-500"}`} />
              <div>
                <span className="text-sm font-mono font-semibold">{p.ticker}</span>
                <span className="text-xs text-muted-foreground ml-2">
                  {p.condition === "below" ? "Stop loss" : "Breakout"} at ₹{p.target_price.toLocaleString()}
                </span>
              </div>
            </div>
            <div className="text-right">
              <p className={`text-sm font-bold ${p.status === "imminent" ? "text-red-500" : "text-amber-500"}`}>
                {p.distance_pct.toFixed(1)}% away
              </p>
              <p className="text-[10px] text-muted-foreground">
                Now: ₹{p.current_price.toLocaleString()}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// SMART SUGGESTIONS
// ============================================================
function SmartSuggestions() {
  const { data: suggestions, isLoading } = useQuery({
    queryKey: ["alert-suggestions"],
    queryFn: () => apiFetch<any[]>("/alerts/suggestions"),
    staleTime: 5 * 60_000,
  });
  const createAlert = useCreateAlert();

  if (isLoading) return <div className="bento-card h-24 skeleton-shimmer" />;
  if (!suggestions || suggestions.length === 0) return null;

  const handleQuickCreate = (s: any) => {
    createAlert.mutate(
      { ticker: s.ticker, target_price: s.target_price, condition: s.condition },
      {
        onSuccess: () => showToast({ title: `Alert created for ${s.ticker}`, variant: "success" }),
      }
    );
  };

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-1">
        <Sparkles className="h-4 w-4 text-primary" />
        Smart Suggestions
      </h3>
      <p className="text-xs text-muted-foreground mb-3">
        Auto-generated from your portfolio's technicals. One tap to activate.
      </p>

      <div className="space-y-2">
        {suggestions.slice(0, 6).map((s: any, i: number) => (
          <div
            key={i}
            className="flex items-center justify-between p-3 rounded-lg border bg-secondary/20 hover:bg-secondary/40 transition-colors"
          >
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                s.type === "stop_loss" ? "bg-red-500/10" : "bg-emerald-500/10"
              }`}>
                {s.type === "stop_loss" ? (
                  <Shield className="h-4 w-4 text-red-500" />
                ) : (
                  <TrendingUp className="h-4 w-4 text-emerald-500" />
                )}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono font-semibold">{s.ticker}</span>
                  <span className={`badge ${s.type === "stop_loss" ? "badge-danger" : "badge-success"}`}>
                    {s.type === "stop_loss" ? "Stop Loss" : "Breakout"}
                  </span>
                  <span className="text-xs text-muted-foreground">₹{s.target_price.toLocaleString()}</span>
                </div>
                <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{s.reason}</p>
              </div>
            </div>
            <button
              onClick={() => handleQuickCreate(s)}
              disabled={createAlert.isPending}
              className="btn-ghost text-xs shrink-0 ml-2"
            >
              <Plus className="h-3 w-3 mr-1" />
              Set
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// CREATE ALERT
// ============================================================
function CreateAlertCard() {
  const [ticker, setTicker] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [condition, setCondition] = useState<"above" | "below">("above");
  const [showForm, setShowForm] = useState(false);

  const createAlert = useCreateAlert();

  const presets = [
    { label: "Stop Loss", condition: "below" as const, icon: Shield, color: "text-red-500", desc: "Alert when price drops below target" },
    { label: "New High", condition: "above" as const, icon: TrendingUp, color: "text-emerald-500", desc: "Alert when price breaks above target" },
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker || !targetPrice) return;

    createAlert.mutate(
      { ticker: ticker.toUpperCase(), target_price: parseFloat(targetPrice), condition },
      {
        onSuccess: () => {
          showToast({ title: `Alert set for ${ticker.toUpperCase()}`, variant: "success" });
          setTicker("");
          setTargetPrice("");
          setShowForm(false);
        },
        onError: () => {
          showToast({ title: "Failed to create alert", variant: "error" });
        },
      }
    );
  };

  return (
    <div className="bento-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold flex items-center gap-2">
          <Plus className="h-4 w-4 text-primary" />
          Set New Alert
        </h3>
      </div>

      {!showForm ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {presets.map((preset) => (
            <button
              key={preset.label}
              onClick={() => {
                setCondition(preset.condition);
                setShowForm(true);
              }}
              className="flex items-center gap-3 p-4 rounded-lg border bg-secondary/30 hover:bg-secondary/60 transition-all duration-150 hover:scale-[1.01] active:scale-[0.99] text-left"
            >
              <div className={`h-9 w-9 rounded-lg flex items-center justify-center bg-background border`}>
                <preset.icon className={`h-4 w-4 ${preset.color}`} />
              </div>
              <div>
                <p className="text-sm font-semibold">{preset.label}</p>
                <p className="text-[11px] text-muted-foreground">{preset.desc}</p>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4 animate-fade-in">
          <div className="flex items-center gap-2 mb-2">
            {condition === "below" ? (
              <span className="badge badge-danger">Stop Loss Alert</span>
            ) : (
              <span className="badge badge-success">New High Alert</span>
            )}
            <button
              type="button"
              onClick={() => setCondition(condition === "above" ? "below" : "above")}
              className="text-[11px] text-primary hover:underline"
            >
              Switch to {condition === "above" ? "stop loss" : "new high"}
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Ticker</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                required
                placeholder="RELIANCE"
                className="input-field font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5 text-muted-foreground">
                Target Price (₹)
              </label>
              <input
                type="number"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
                required
                min="0.01"
                step="any"
                placeholder="1200.00"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Condition</label>
              <select
                value={condition}
                onChange={(e) => setCondition(e.target.value as "above" | "below")}
                className="input-field"
              >
                <option value="above">Price goes above</option>
                <option value="below">Price drops below</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button type="submit" disabled={createAlert.isPending} className="btn-primary">
              <Zap className="h-3.5 w-3.5 mr-1.5" />
              {createAlert.isPending ? "Creating..." : "Create Alert"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-ghost text-xs">
              Cancel
            </button>
          </div>

          <p className="text-[11px] text-muted-foreground">
            You'll receive a Telegram notification when this price level is hit during market hours.
          </p>
        </form>
      )}
    </div>
  );
}

// ============================================================
// ACTIVE ALERTS
// ============================================================
function ActiveAlerts() {
  const { data: alerts, isLoading } = useAlerts();
  const deleteAlert = useDeleteAlert();

  const activeAlerts = (alerts || []).filter((a: any) => a.status === "active");

  if (isLoading) {
    return (
      <div className="bento-card">
        <div className="h-5 w-32 skeleton rounded mb-4" />
        <div className="space-y-2">
          <div className="h-16 skeleton-shimmer rounded-lg" />
          <div className="h-16 skeleton-shimmer rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <BellRing className="h-4 w-4 text-amber-500" />
        Active Alerts
        {activeAlerts.length > 0 && (
          <span className="text-xs font-normal text-muted-foreground">({activeAlerts.length})</span>
        )}
      </h3>

      {activeAlerts.length === 0 ? (
        <div className="text-center py-8 text-sm text-muted-foreground">
          <Bell className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p>No active alerts</p>
          <p className="text-xs mt-1 text-muted-foreground/70">Create one above to start monitoring</p>
        </div>
      ) : (
        <div className="space-y-2">
          {activeAlerts.map((alert: any) => (
            <div
              key={alert.id}
              className="flex items-center justify-between p-3 rounded-lg border bg-secondary/20 hover:bg-secondary/40 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${
                  alert.condition === "below" ? "bg-red-500/10" : "bg-emerald-500/10"
                }`}>
                  {alert.condition === "below" ? (
                    <TrendingDown className="h-4 w-4 text-red-500" />
                  ) : (
                    <TrendingUp className="h-4 w-4 text-emerald-500" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold font-mono">{alert.ticker}</span>
                    <span className={`badge ${alert.condition === "below" ? "badge-danger" : "badge-success"}`}>
                      {alert.condition === "below" ? "Stop Loss" : "New High"}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Alert when price goes {alert.condition} <strong>₹{Number(alert.target_price).toLocaleString()}</strong>
                  </p>
                </div>
              </div>

              <button
                onClick={() => {
                  deleteAlert.mutate(alert.id, {
                    onSuccess: () => showToast({ title: "Alert removed", variant: "default" }),
                  });
                }}
                className="btn-icon text-muted-foreground hover:text-destructive"
                aria-label="Delete alert"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// TRIGGERED HISTORY
// ============================================================
function TriggeredHistory() {
  const { data: alerts } = useAlerts();
  const triggeredAlerts = (alerts || []).filter((a: any) => a.status === "triggered");

  if (triggeredAlerts.length === 0) return null;

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
        Triggered History
        <span className="text-xs font-normal text-muted-foreground">({triggeredAlerts.length})</span>
      </h3>

      <div className="space-y-2">
        {triggeredAlerts.slice(0, 10).map((alert: any) => (
          <div
            key={alert.id}
            className="flex items-center justify-between p-3 rounded-lg border border-border/50 opacity-70"
          >
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium font-mono">{alert.ticker}</span>
                  <span className="text-[10px] text-muted-foreground">
                    {alert.condition} ₹{Number(alert.target_price).toLocaleString()}
                  </span>
                </div>
                {alert.triggered_at && (
                  <p className="text-[11px] text-muted-foreground">
                    Triggered: {new Date(alert.triggered_at).toLocaleString([], {
                      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                    })}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
