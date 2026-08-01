import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { useActivePortfolio } from "@/contexts/PortfolioContext";
import { Settings, Globe, Save, Plus, Trash2, Star, Loader2 } from "lucide-react";
import type { BrokerId } from "@/api/types";

interface GeoOption {
  geo_id: string;
  display_name: string;
  currency_symbol: string;
  currency_code: string;
  exchanges: string[];
}

const BROKER_OPTIONS: { id: BrokerId | ""; label: string; geo: string[] }[] = [
  { id: "", label: "None", geo: ["IN", "US"] },
  { id: "groww", label: "Groww", geo: ["IN"] },
  { id: "zerodha", label: "Zerodha", geo: ["IN"] },
  { id: "robinhood", label: "Robinhood", geo: ["US"] },
  { id: "fidelity", label: "Fidelity", geo: ["US"] },
];

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: prefs, isLoading } = useQuery({
    queryKey: ["user-preferences"],
    queryFn: () => apiFetch<any>("/user/preferences"),
  });
  const { data: geos } = useQuery({
    queryKey: ["geographies"],
    queryFn: () => apiFetch<GeoOption[]>("/user/geographies"),
  });

  const [geography, setGeography] = useState("");
  const [saved, setSaved] = useState(false);

  const updateMutation = useMutation({
    mutationFn: (body: any) => apiFetch("/user/preferences", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      setTimeout(() => window.location.reload(), 500);
    },
  });

  if (isLoading) return <div className="bento-card h-40 skeleton-shimmer" />;

  const currentGeo = geography || prefs?.geography || "IN";

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Settings className="h-6 w-6 text-muted-foreground" />
          Settings
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage portfolios, geography, and preferences
        </p>
      </div>

      {/* Portfolio Management */}
      <PortfolioManagement geos={geos || []} />

      {/* Geography Preferences */}
      <div className="bento-card max-w-lg">
        <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
          <Globe className="h-4 w-4 text-primary" />
          Default Geography
        </h3>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5 text-muted-foreground">
              Market Geography
            </label>
            <select
              value={currentGeo}
              onChange={(e) => setGeography(e.target.value)}
              className="input-field"
            >
              {(geos || []).map((g) => (
                <option key={g.geo_id} value={g.geo_id}>
                  {g.display_name} ({g.currency_symbol} {g.currency_code}) — {g.exchanges.join(", ")}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-muted-foreground">Currency:</span>
              <span className="ml-2 font-medium">{prefs?.currency_symbol} ({prefs?.currency_code})</span>
            </div>
            <div>
              <span className="text-muted-foreground">Locale:</span>
              <span className="ml-2 font-medium">{prefs?.locale}</span>
            </div>
          </div>

          <button
            onClick={() => updateMutation.mutate({ geography: currentGeo })}
            disabled={updateMutation.isPending || currentGeo === prefs?.geography}
            className="btn-primary text-xs"
          >
            <Save className="h-3.5 w-3.5 mr-1.5" />
            {saved ? "Saved!" : updateMutation.isPending ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PortfolioManagement({ geos }: { geos: GeoOption[] }) {
  const queryClient = useQueryClient();
  const { portfolios, activePortfolio, refresh: refreshPortfolios } = useActivePortfolio();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newGeo, setNewGeo] = useState("IN");
  const [newBroker, setNewBroker] = useState<string>("");
  const [creating, setCreating] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiFetch(`/portfolios/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      refreshPortfolios();
    },
    onError: (e: any) => {
      const msg = e?.body?.detail || "Cannot delete portfolio";
      alert(msg);
    },
  });

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/portfolios/${id}`, {
        method: "PUT",
        body: JSON.stringify({ is_default: true }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      refreshPortfolios();
    },
  });

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await apiFetch("/portfolios", {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          geo_id: newGeo,
          broker_id: newBroker || null,
        }),
      });
      setShowCreate(false);
      setNewName("");
      setNewBroker("");
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      refreshPortfolios();
    } catch (e: any) {
      const msg = e?.body?.detail || "Failed to create";
      alert(msg);
    } finally {
      setCreating(false);
    }
  };

  const availableBrokers = BROKER_OPTIONS.filter((b) => b.geo.includes(newGeo));

  return (
    <div className="bento-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold">My Portfolios</h3>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-3 w-3" />
          Add
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="rounded-lg border bg-muted/30 p-3 mb-4 space-y-3 animate-fade-in">
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="US Growth"
                className="w-full rounded-md border px-2.5 py-1.5 text-xs bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">Geography</label>
              <select
                value={newGeo}
                onChange={(e) => { setNewGeo(e.target.value); setNewBroker(""); }}
                className="w-full rounded-md border px-2.5 py-1.5 text-xs bg-background"
              >
                {geos.map((g) => (
                  <option key={g.geo_id} value={g.geo_id}>
                    {g.display_name} ({g.currency_symbol})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">Broker</label>
              <select
                value={newBroker}
                onChange={(e) => setNewBroker(e.target.value)}
                className="w-full rounded-md border px-2.5 py-1.5 text-xs bg-background"
              >
                {availableBrokers.map((b) => (
                  <option key={b.id} value={b.id}>{b.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={creating || !newName.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {creating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="rounded-md border px-3 py-1.5 text-xs hover:bg-secondary/50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Portfolio list */}
      <div className="space-y-2">
        {portfolios.map((p) => (
          <div
            key={p.id}
            className={`flex items-center justify-between rounded-lg border p-3 transition-colors ${
              p.id === activePortfolio?.id ? "border-primary/40 bg-primary/5" : ""
            }`}
          >
            <div className="flex items-center gap-3">
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium">{p.name}</span>
                  {p.is_default && (
                    <span className="rounded-full bg-primary/10 text-primary px-1.5 py-0.5 text-[9px] font-medium">
                      Default
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {p.display_name} · {p.currency_symbol} {p.currency_code}
                  {p.broker_id && ` · ${p.broker_id}`}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              {!p.is_default && (
                <button
                  onClick={() => setDefaultMutation.mutate(p.id)}
                  disabled={setDefaultMutation.isPending}
                  title="Set as default"
                  className="p-1.5 rounded-md hover:bg-secondary/50 text-muted-foreground hover:text-primary transition-colors"
                >
                  <Star className="h-3.5 w-3.5" />
                </button>
              )}
              {!p.is_default && portfolios.length > 1 && (
                <button
                  onClick={() => {
                    if (confirm(`Delete "${p.name}"?`)) {
                      deleteMutation.mutate(p.id);
                    }
                  }}
                  disabled={deleteMutation.isPending}
                  title="Delete portfolio"
                  className="p-1.5 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
