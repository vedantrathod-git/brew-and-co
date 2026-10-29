/**
 * Reusable formatting utilities for the Restaurant Management System.
 * Phase 12: Centralized USD currency presentation.
 */

// Centralized Intl.NumberFormat instance configured for US Dollars (USD)
const usdCurrencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Formats a monetary amount into US Dollars (e.g. $12.50, $1,250.00).
 * Handles null, undefined, numeric strings, and Decimal representations gracefully without altering stored numbers.
 *
 * @param {number|string|null|undefined} amount - The numeric price to format.
 * @returns {string} Formatted currency string in USD (e.g. "$12.50").
 */
export function formatUSD(amount) {
  if (amount === undefined || amount === null || amount === '') {
    return usdCurrencyFormatter.format(0);
  }
  const num = Number(amount);
  if (Number.isNaN(num)) {
    return usdCurrencyFormatter.format(0);
  }
  return usdCurrencyFormatter.format(num);
}

// Canonical alias for formatUSD
export const formatCurrency = formatUSD;

// Backward-compatible alias for existing imports
export const formatINR = formatUSD;

/**
 * Formats an ISO date-time string into a human-readable format.
 * Example: "21 Oct 2026, 03:30 PM"
 *
 * @param {string|Date} isoString - ISO date string
 * @returns {string} Formatted date-time string
 */
export function formatDateTime(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString('en-US', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return '—';
  }
}

/**
 * Formats an ISO date-time string into a concise time string.
 * Example: "03:30 PM"
 *
 * @param {string|Date} isoString - ISO date string
 * @returns {string} Formatted time string
 */
export function formatTime(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return '—';
  }
}
