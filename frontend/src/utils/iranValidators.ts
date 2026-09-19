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

/**
 * VIN (Vehicle Identification Number): exactly 17 characters, uppercase
 * letters and digits only, excluding I, O, and Q (they're never used in real
 * VINs because they're easily confused with 1 and 0). e.g. 1HGCM82633A004352
 */
export const VIN_REGEX = /^[A-HJ-NPR-Z0-9]{17}$/i;

/**
 * OBU serial number: "OBU-" followed by a 4-digit year and a numeric
 * sequence of at least 4 digits, e.g. OBU-2026-0001. Keep in sync with
 * `backend/fleet_monitoring/validators.py`.
 */
export const OBU_SERIAL_REGEX = /^OBU-\d{4}-\d{4,}$/i;

/**
 * Driver's license number: exactly 10 digits, per the Iranian driver's
 * license format. e.g. 1234567890
 */
export const IRAN_LICENSE_NUMBER_REGEX = /^\d{10}$/;
