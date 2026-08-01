import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { Settings, Globe, Save } from "lucide-react";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: prefs, isLoading } = useQuery({
    queryKey: ["user-preferences"],
    queryFn: () => apiFetch<any>("/user/preferences"),
  });
  const { data: geos } = useQuery({
    queryKey: ["geographies"],
    queryFn: () => apiFetch<any[]>("/user/geographies"),
  });

  const [geography, setGeography] = useState("");
  const [saved, setSaved] = useState(false);

  const updateMutation = useMutation({
    mutationFn: (body: any) => apiFetch("/user/preferences", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      // Reload to apply new geo context
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
          Configure your geography, currency, and display preferences
        </p>
      </div>

      <div className="bento-card max-w-lg">
        <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
          <Globe className="h-4 w-4 text-primary" />
          Geography & Market
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
              {(geos || []).map((g: any) => (
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
            <div>
              <span className="text-muted-foreground">Exchanges:</span>
              <span className="ml-2 font-medium">{prefs?.exchanges?.join(", ")}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Dividends:</span>
              <span className="ml-2 font-medium capitalize">{prefs?.dividend_frequency}</span>
            </div>
          </div>

          <button
            onClick={() => updateMutation.mutate({ geography: currentGeo })}
            disabled={updateMutation.isPending || currentGeo === prefs?.geography}
            className="btn-primary text-xs"
          >
            <Save className="h-3.5 w-3.5 mr-1.5" />
            {saved ? "Saved!" : updateMutation.isPending ? "Saving..." : "Save Preferences"}
          </button>
        </div>
      </div>
    </div>
  );
}
