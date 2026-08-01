/**
 * Portfolio Context — manages active portfolio selection.
 *
 * Fetches user's portfolios, tracks which one is active.
 * All data-fetching pages use activePortfolio to scope queries.
 */

import { createContext, useContext, useEffect, useState } from "react";
import { apiFetch } from "@/api/client";

interface PortfolioItem {
  id: string;
  name: string;
  geo_id: string;
  broker_id: string | null;
  is_default: boolean;
  currency_symbol: string;
  currency_code: string;
  display_name: string;
}

interface PortfolioContextValue {
  portfolios: PortfolioItem[];
  activePortfolio: PortfolioItem | null;
  setActivePortfolio: (id: string) => void;
  isLoading: boolean;
  isMultiPortfolio: boolean;
  refresh: () => void;
}

const PortfolioContext = createContext<PortfolioContextValue>({
  portfolios: [],
  activePortfolio: null,
  setActivePortfolio: () => {},
  isLoading: true,
  isMultiPortfolio: false,
  refresh: () => {},
});

export function PortfolioProvider({ children }: { children: React.ReactNode }) {
  const [portfolios, setPortfolios] = useState<PortfolioItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchPortfolios = () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setIsLoading(false);
      return;
    }

    apiFetch<PortfolioItem[]>("/portfolios")
      .then((data) => {
        setPortfolios(data);
        // Set active to default or first
        const defaultP = data.find((p) => p.is_default) || data[0];
        if (defaultP && !activeId) {
          setActiveId(defaultP.id);
        }
        setIsLoading(false);
      })
      .catch(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const activePortfolio = portfolios.find((p) => p.id === activeId) || portfolios[0] || null;

  return (
    <PortfolioContext.Provider
      value={{
        portfolios,
        activePortfolio,
        setActivePortfolio: setActiveId,
        isLoading,
        isMultiPortfolio: portfolios.length > 1,
        refresh: fetchPortfolios,
      }}
    >
      {children}
    </PortfolioContext.Provider>
  );
}

export function useActivePortfolio() {
  return useContext(PortfolioContext);
}
