/**
 * Geography Context — provides currency/locale/geography to all components.
 *
 * Fetches user preferences on mount. Falls back to India (INR) defaults.
 * All components that format money should use useGeo().formatCurrency() instead of hardcoded "₹".
 */

import { createContext, useContext, useEffect, useState } from "react";
import { apiFetch } from "@/api/client";

interface GeoContextValue {
  geography: string;
  currencyCode: string;
  currencySymbol: string;
  locale: string;
  displayName: string;
  exchanges: string[];
  dividendFrequency: string;
  isLoading: boolean;
  formatCurrency: (value: number) => string;
  formatCurrencyCompact: (value: number) => string;
}

const DEFAULT_GEO: GeoContextValue = {
  geography: "IN",
  currencyCode: "INR",
  currencySymbol: "₹",
  locale: "en-IN",
  displayName: "India",
  exchanges: ["NSE", "BSE"],
  dividendFrequency: "annual",
  isLoading: true,
  formatCurrency: (v) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2, minimumFractionDigits: 0 }).format(v),
  formatCurrencyCompact: (v) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(v),
};

const GeoContext = createContext<GeoContextValue>(DEFAULT_GEO);

export function GeoProvider({ children }: { children: React.ReactNode }) {
  const [geo, setGeo] = useState<GeoContextValue>(DEFAULT_GEO);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setGeo((prev) => ({ ...prev, isLoading: false }));
      return;
    }

    apiFetch<any>("/user/preferences")
      .then((data) => {
        const currencyCode = data.currency_code || "INR";
        const locale = data.locale || "en-IN";

        setGeo({
          geography: data.geography || "IN",
          currencyCode,
          currencySymbol: data.currency_symbol || "₹",
          locale,
          displayName: data.display_name || "India",
          exchanges: data.exchanges || ["NSE", "BSE"],
          dividendFrequency: data.dividend_frequency || "annual",
          isLoading: false,
          formatCurrency: (v: number) =>
            new Intl.NumberFormat(locale, { style: "currency", currency: currencyCode, maximumFractionDigits: 2, minimumFractionDigits: 0 }).format(v),
          formatCurrencyCompact: (v: number) =>
            new Intl.NumberFormat(locale, { style: "currency", currency: currencyCode, maximumFractionDigits: 0 }).format(v),
        });
      })
      .catch(() => {
        setGeo((prev) => ({ ...prev, isLoading: false }));
      });
  }, []);

  return <GeoContext.Provider value={geo}>{children}</GeoContext.Provider>;
}

export function useGeo(): GeoContextValue {
  return useContext(GeoContext);
}
