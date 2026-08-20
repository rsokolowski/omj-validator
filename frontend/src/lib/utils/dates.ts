/**
 * Date formatting utilities for consistent timestamp display.
 *
 * All timestamps from the backend are in UTC (ISO 8601 with timezone).
 * These utilities format them in the user's local timezone.
 */

/**
 * Format an ISO datetime string to a localized date/time string.
 *
 * The timestamp is displayed in the user's local timezone using Polish locale
 * formatting (DD.MM.YYYY, HH:MM).
 *
 * @param dateString - ISO 8601 datetime string from the API (e.g., "2024-01-15T14:30:00+00:00")
 * @returns Formatted string like "15.01.2024, 15:30" (in local timezone)
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  // Handle invalid date strings gracefully
  if (isNaN(date.getTime())) {
    return dateString;
  }
  return new Intl.DateTimeFormat("pl-PL", {
    timeZone: "Europe/Warsaw",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/**
 * Format an ISO datetime string to a short date string (no time).
 *
 * @param dateString - ISO 8601 datetime string from the API
 * @returns Formatted string like "15.01.2024" (in local timezone)
 */
export function formatDateShort(dateString: string): string {
  const date = new Date(dateString);
  // Handle invalid date strings gracefully
  if (isNaN(date.getTime())) {
    return dateString;
  }
  return new Intl.DateTimeFormat("pl-PL", {
    timeZone: "Europe/Warsaw",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

/**
 * Format an ISO datetime string to a relative time string.
 *
 * @param dateString - ISO 8601 datetime string from the API
 * @returns Relative time like "2 godziny temu", "wczoraj", etc.
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  // Handle invalid date strings gracefully
  if (isNaN(date.getTime())) {
    return dateString;
  }
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSec < 60) {
    return "przed chwilą";
  }
  if (diffMin < 60) {
    return `${diffMin} min temu`;
  }
  if (diffHours < 24) {
    return `${diffHours} godz. temu`;
  }
  if (diffDays === 1) {
    return "wczoraj";
  }
  if (diffDays < 7) {
    return `${diffDays} dni temu`;
  }

  // Fall back to full date for older dates
  return formatDate(dateString);
}
