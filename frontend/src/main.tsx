import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GeoProvider } from "@/contexts/GeoContext";
import { PortfolioProvider } from "@/contexts/PortfolioContext";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // 30 seconds — aligns with price cache TTL
      retry: 2,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <GeoProvider>
        <PortfolioProvider>
          <App />
        </PortfolioProvider>
      </GeoProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
