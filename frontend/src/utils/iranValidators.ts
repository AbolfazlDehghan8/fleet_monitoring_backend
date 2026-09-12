/**
 * Iran-specific field formats, shared across form schemas so the frontend
 * rejects the exact same things the backend does (fail fast, before a
 * round-trip to the API).
 *
 * Keep these in sync with backend/fleet_monitoring/validators.py.
 */

/** Mobile phone: exactly 11 digits, starting with "09". e.g. 09123456789 */
export const IRAN_MOBILE_REGEX = /^09\d{9}$/;

/**
 * Phone (mobile or landline with area code): exactly 11 digits, starting
 * with "0". e.g. 09123456789 or 02112345678
 */
export const IRAN_PHONE_REGEX = /^0\d{10}$/;

/**
 * Civilian license plate: 2 digits + 1 Persian letter + 3 digits + 2-digit
 * province/city code, no spaces or dashes. e.g. 12ب34567
 */
const IRAN_PLATE_LETTERS =
  'الف|ب|پ|ت|ث|ج|د|ز|س|ش|ص|ط|ع|ف|ق|ک|گ|ل|م|ن|و|ه|ی';
export const IRAN_PLATE_REGEX = new RegExp(
  `^\\d{2}(${IRAN_PLATE_LETTERS})\\d{3}\\d{2}$`,
);
