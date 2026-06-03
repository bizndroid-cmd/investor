import { useState, useMemo } from "react";
import { usePortfolio } from "@/hooks/usePortfolio";
import { useUIStore } from "@/stores/uiStore";
import { HoldingRow } from "./HoldingRow";
import type { NormalizedHolding } from "@/api/types";

type SortKey = keyof Pick<
  NormalizedHolding,
  "ticker" | "company_name" | "broker_id" | "quantity" | "current_value" | "gain_loss_percent"
>;

export function HoldingsTable() {
  const { data: portfolio, isLoading } = usePortfolio();
  const activeBrokerFilter = useUIStore((s) => s.activeBrokerFilter);
  const [sortKey, setSortKey] = useState<SortKey>("ticker");
  const [sortAsc, setSortAsc] = useState(true);

  const holdings = useMemo(() => {
    if (!portfolio) return [];
    let filtered = portfolio.holdings;
    if (activeBrokerFilter) {
      filtered = filtered.filter((h) => h.broker_id === activeBrokerFilter);
    }
    return [...filtered].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortAsc ? aVal - bVal : bVal - aVal;
      }
      return sortAsc
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal));
    });
  }, [portfolio, activeBrokerFilter, sortKey, sortAsc]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  if (isLoading) {
    return <div className="animate-pulse h-40 bg-muted rounded-lg" aria-busy="true" />;
  }

  const columns: { key: SortKey; label: string; align?: string }[] = [
    { key: "ticker", label: "Ticker" },
    { key: "company_name", label: "Company" },
    { key: "broker_id", label: "Broker" },
    { key: "quantity", label: "Qty", align: "text-right" },
    { key: "ticker", label: "Avg Cost", align: "text-right" },
    { key: "ticker", label: "Price", align: "text-right" },
    { key: "current_value", label: "Value", align: "text-right" },
    { key: "gain_loss_percent", label: "Gain/Loss %", align: "text-right" },
  ];

  return (
    <div className="rounded-lg border overflow-x-auto">
      <table className="w-full text-sm" aria-label="Holdings table">
        <thead>
          <tr className="border-b bg-muted/50">
            {columns.map((col, i) => (
              <th
                key={i}
                className={`px-3 py-2 font-medium text-muted-foreground cursor-pointer select-none ${col.align || "text-left"}`}
                onClick={() => handleSort(col.key)}
                aria-sort={
                  sortKey === col.key
                    ? sortAsc
                      ? "ascending"
                      : "descending"
                    : "none"
                }
              >
                {col.label}
                {sortKey === col.key && (
                  <span className="ml-1">{sortAsc ? "↑" : "↓"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {holdings.length === 0 ? (
            <tr>
              <td colSpan={8} className="px-3 py-8 text-center text-muted-foreground">
                No holdings found.
              </td>
            </tr>
          ) : (
            holdings.map((holding, i) => (
              <HoldingRow key={`${holding.broker_id}-${holding.ticker}-${i}`} holding={holding} />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
