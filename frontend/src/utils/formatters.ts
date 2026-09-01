import { format, formatDistanceToNow, parseISO } from 'date-fns';

/** Safely parse a value that might already be a Date or an ISO string. */
function toDate(value: string | Date): Date {
  return typeof value === 'string' ? parseISO(value) : value;
}

/** e.g. "Aug 29, 2026, 3:45 PM" */
export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return '—';
  try {
    return format(toDate(value), 'MMM d, yyyy, h:mm a');
  } catch {
    return '—';
  }
}

/** e.g. "3:45:12 PM" — used in dense telemetry tables. */
export function formatTime(value: string | Date | null | undefined): string {
  if (!value) return '—';
  try {
    return format(toDate(value), 'h:mm:ss a');
  } catch {
    return '—';
  }
}

/** e.g. "2 minutes ago" */
export function formatRelativeTime(value: string | Date | null | undefined): string {
  if (!value) return '—';
  try {
    return formatDistanceToNow(toDate(value), { addSuffix: true });
  } catch {
    return '—';
  }
}

export function formatNumber(value: number | null | undefined, fractionDigits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

export function formatSpeed(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${formatNumber(value, 0)} km/h`;
}

export function formatFuel(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${formatNumber(value, 0)}%`;
}

export function formatTemperature(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${formatNumber(value, 1)}°C`;
}

export function formatVoltage(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${formatNumber(value, 1)}V`;
}

export function formatOdometer(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${formatNumber(value, 0)} km`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export function initials(firstName?: string, lastName?: string, fallback = 'U'): string {
  const first = firstName?.trim()?.[0] ?? '';
  const last = lastName?.trim()?.[0] ?? '';
  const combined = `${first}${last}`.toUpperCase();
  return combined || fallback;
}

export function titleCase(value: string): string {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
