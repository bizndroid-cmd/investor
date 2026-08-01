/**
 * Currency formatting utility for multi-geography support.
 *
 * Uses Intl.NumberFormat for locale-aware formatting.
 * Replaces all hardcoded "₹" and "en-IN" formatting.
 *
 * Usage:
 *   formatCurrency(100000, "INR", "en-IN")  → "₹1,00,000.00"
 *   formatCurrency(100000, "USD", "en-US")  → "$100,000.00"
 */

/**
 * Format a monetary value with locale-appropriate currency symbol and grouping.
 */
export function formatCurrency(
  value: number,
  currencyCode: string,
  locale: string
): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currencyCode,
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(value);
}

/**
 * Format a monetary value without decimal places (for large round numbers).
 */
export function formatCurrencyCompact(
  value: number,
  currencyCode: string,
  locale: string
): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currencyCode,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Format a percentage value with sign indicator.
 */
export function formatPercent(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}
