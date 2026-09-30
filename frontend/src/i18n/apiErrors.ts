/**
 * The Django/DRF backend is English-only and returns raw English validation
 * and permission messages (e.g. "Invalid username or password", "This field
 * is required."). Historically the frontend displayed those bodies verbatim
 * via `ApiError.extractMessage`, which meant English text leaked into the
 * Persian UI (toast descriptions, login/register server errors, etc.).
 *
 * `getApiErrorMessage` maps every known backend message to a translated
 * string. Anything unrecognized falls back to a translated generic message
 * instead of the raw text, so nothing in the UI's own language is ever
 * displayed in the other language.
 */

import type { ApiErrorBody } from '@/types/common';
import type { TranslationKey } from '@/i18n/translations';

type Translate = (key: TranslationKey, vars?: Record<string, string | number>) => string;

const FIELD_LABEL_KEYS: Record<string, TranslationKey> = {
  username: 'apiError.field.username',
  email: 'apiError.field.email',
  license_plate: 'apiError.field.license_plate',
  vin: 'apiError.field.vin',
  vehicle_id: 'apiError.field.vehicle_id',
  serial_number: 'apiError.field.serial_number',
  obu_serial_number: 'apiError.field.serial_number',
  obu_serial: 'apiError.field.serial_number',
  license_number: 'apiError.field.license_number',
  phone_number: 'apiError.field.phone_number',
};

/** metric field name -> its existing `ruleMetric.*` label key, reused for error messages. */
const RULE_METRIC_LABEL_KEYS: Record<string, TranslationKey> = {
  speed: 'ruleMetric.speed',
  engine_temperature: 'ruleMetric.engine_temperature',
  battery_voltage: 'ruleMetric.battery_voltage',
  fuel_level: 'ruleMetric.fuel_level',
  odometer: 'ruleMetric.odometer',
};

/** Exact raw backend message -> translation key. */
const EXACT_MESSAGES: Record<string, TranslationKey> = {
  'Invalid username or password': 'apiError.invalidCredentials',
  'User account is disabled': 'apiError.accountDisabled',
  'This user already has a driver profile': 'apiError.driverProfileExists',
  'Company not found': 'apiError.companyNotFound',
  'Could not save record due to a conflicting record': 'apiError.conflictingRecord',
  'start_date must be before end_date': 'apiError.startBeforeEndDate',
  'Passwords do not match': 'register.errorPasswordMismatch',
  'Username already exists': 'apiError.usernameExists',
  'Email already exists': 'apiError.emailExists',
  'Could not create user due to a conflicting record': 'apiError.conflictingUser',
  'User not found': 'apiError.userNotFound',
  'Driver not found': 'apiError.driverNotFound',
  'Report not found': 'apiError.reportNotFound',
  'Alert not found': 'apiError.alertNotFound',
  'No vehicle found with this vehicle_id': 'apiError.noVehicleWithId',
  'Telemetry logs are immutable and cannot be updated.': 'apiError.telemetryImmutableUpdate',
  'Telemetry logs are immutable and cannot be deleted.': 'apiError.telemetryImmutableDelete',
  'Rule not found': 'apiError.ruleNotFound',
  'A rule with the same metric, operator, and threshold already exists.': 'apiError.ruleDuplicate',
  'Vehicle not found': 'apiError.vehicleNotFound',
  'This vehicle is not assigned to you': 'apiError.vehicleNotAssigned',
  'This alert is not on a vehicle assigned to you': 'apiError.alertNotAssigned',
  'This alert is not on your vehicle': 'apiError.alertNotAssigned',
  'This report was not requested by you': 'apiError.reportNotYours',
  'Unknown role': 'apiError.unknownRole',
  'Drivers must use /api/v1/vehicles/me/': 'apiError.driversUseMeEndpoint',
  'You do not have access to this vehicle': 'apiError.noVehicleAccess',
  'Only admin can delete vehicles': 'apiError.adminOnlyDeleteVehicles',
  'Only admin and fleet_manager may view dashboard stats': 'apiError.adminManagerOnlyDashboard',
  'Drivers do not have access to the drivers list': 'apiError.driversNoAccessList',
  'Only admin and fleet_manager may browse driver-role users': 'apiError.adminManagerOnlyBrowseDrivers',
  'Only admin can delete driver profiles': 'apiError.adminOnlyDeleteDriverProfiles',
  'Only admin can update company information': 'apiError.adminOnlyUpdateCompany',
  'Only admins may provision users.': 'apiError.adminOnlyProvisionUsers',
  'Only admins may update other users.': 'apiError.adminOnlyUpdateUsers',
  'Only admins may delete users.': 'apiError.adminOnlyDeleteUsers',
  'Linked user must have the driver role': 'apiError.linkedUserMustBeDriver',
  'Assigned manager must have the fleet_manager role': 'apiError.managerMustBeFleetManager',
  'Invalid token type. Use refresh token.': 'apiError.invalidTokenType',
  'Invalid refresh token': 'apiError.invalidRefreshToken',
  'Refresh token has been revoked or does not exist': 'apiError.refreshTokenRevoked',
  'Refresh token has been revoked': 'apiError.refreshTokenRevoked',
  'Refresh token has expired': 'apiError.refreshTokenExpired',
  'Current password is incorrect': 'apiError.currentPasswordIncorrect',
  'New password must be different from the current password': 'apiError.newPasswordSameAsOld',
  'Access token has expired': 'apiError.accessTokenExpired',
  'Invalid token': 'apiError.invalidToken',
  'This field is required.': 'apiError.fieldRequired',
  'This field may not be blank.': 'apiError.fieldBlank',
  'This field may not be null.': 'apiError.fieldNull',
  'Enter a valid email address.': 'register.errorEmailInvalid',
  'This password is too common.': 'apiError.passwordTooCommon',
  'This password is entirely numeric.': 'apiError.passwordEntirelyNumeric',
  'A valid number is required.': 'apiError.invalidNumber',
  'A valid integer is required.': 'apiError.invalidInteger',
  'License number must be exactly 10 digits.': 'apiError.invalidLicenseNumber',
  'Enter a valid username. This value may contain only unicode letters, numbers, and @/./+/-/_ characters.':
    'apiError.invalidUsernameFormat',
  'Too many failed login attempts. Try again later.': 'apiError.tooManyLoginAttempts',
  'Self-registration is disabled': 'apiError.selfRegistrationDisabled',
  'You cannot demote or deactivate your own account': 'apiError.cannotSelfDemote',
  'You cannot delete your own account': 'apiError.cannotSelfDelete',
  'Cannot remove the last active admin': 'apiError.cannotRemoveLastAdmin',
  'You do not have access to this driver': 'apiError.noDriverAccess',
  'Assigned driver must be active': 'apiError.driverMustBeActive',
  'timestamp is in the future': 'apiError.telemetryTimestampFuture',
  'timestamp is older than the retention period': 'apiError.telemetryTimestampTooOld',
  'OBU serial does not match the OBU registered for this vehicle': 'apiError.obuSerialMismatch',
  'Vehicle is decommissioned and no longer accepts telemetry': 'apiError.vehicleDecommissionedNoTelemetry',
  'Threshold must be a finite number.': 'apiError.thresholdMustBeFinite',
};

/** Parametrized backend messages, matched with a regex. */
const PATTERN_MESSAGES: Array<{
  pattern: RegExp;
  key: TranslationKey;
  vars?: (match: RegExpMatchArray, t: Translate) => Record<string, string | number>;
}> = [
  {
    // e.g. "license_plate already exists" (from _integrity_error_to_validation)
    pattern: /^(\w+) already exists$/i,
    key: 'apiError.fieldAlreadyExists',
    vars: (m, t) => ({ field: fieldLabel(m[1], t) }),
  },
  {
    // Django's built-in username message, e.g. "A user with that username already exists."
    pattern: /^A user with that (\w+) already exists\.$/i,
    key: 'apiError.fieldAlreadyExists',
    vars: (m, t) => ({ field: fieldLabel(m[1], t) }),
  },
  {
    // DRF's automatic unique validator, e.g. "user with this username already exists."
    pattern: /^\w+ with this (\w+) already exists\.$/i,
    key: 'apiError.modelFieldExists',
    vars: (m, t) => ({ field: fieldLabel(m[1], t) }),
  },
  {
    pattern: /^"(.+)" is not a valid choice\.$/,
    key: 'apiError.invalidChoice',
    vars: (m) => ({ value: m[1] }),
  },
  {
    pattern: /^Ensure this field has at least (\d+) characters?\.$/,
    key: 'apiError.minLength',
    vars: (m) => ({ count: m[1] }),
  },
  {
    pattern: /^Ensure this field has no more than (\d+) characters?\.$/,
    key: 'apiError.maxLengthField',
    vars: (m) => ({ count: m[1] }),
  },
  {
    pattern: /^This password is too short\. It must contain at least (\d+) characters?\.$/,
    key: 'apiError.passwordTooShort',
    vars: (m) => ({ count: m[1] }),
  },
  {
    // e.g. "Threshold for battery_voltage must be between 0 and 50."
    pattern: /^Threshold for (\w+) must be between (-?[\d.]+) and (-?[\d.]+)\.$/,
    key: 'apiError.thresholdOutOfRange',
    vars: (m, t) => ({ metric: ruleMetricLabel(m[1], t), min: m[2], max: m[3] }),
  },
  {
    // e.g. "Date range cannot exceed 366 days"
    pattern: /^Date range cannot exceed (\d+) days$/,
    key: 'apiError.dateRangeTooLong',
    vars: (m) => ({ days: m[1] }),
  },
];

function fieldLabel(field: string, t: Translate): string {
  const key = FIELD_LABEL_KEYS[field];
  return key ? t(key) : field;
}

function ruleMetricLabel(metric: string, t: Translate): string {
  const key = RULE_METRIC_LABEL_KEYS[metric];
  return key ? t(key) : metric;
}

/**
 * True when a message is unmistakably raw, untranslated backend English:
 * it has no Persian/Arabic script at all but does have real English words.
 * (Our own Persian-language validator messages, e.g. for plate/VIN formats,
 * are full Persian sentences that merely *contain* a Latin example token —
 * those have Persian characters too, so this stays false for them and they
 * pass through unchanged regardless of which UI language is active.)
 */
function isUntranslatedEnglish(text: string): boolean {
  const hasPersianScript = /[\u0600-\u06FF]/.test(text);
  const hasEnglishWord = /[A-Za-z]{3,}/.test(text);
  return !hasPersianScript && hasEnglishWord;
}

function translateOne(raw: string, t: Translate): string {
  const trimmed = raw.trim();
  const exact = EXACT_MESSAGES[trimmed];
  if (exact) return t(exact);

  for (const { pattern, key, vars } of PATTERN_MESSAGES) {
    const match = trimmed.match(pattern);
    if (match) return t(key, vars ? vars(match, t) : undefined);
  }

  // Unknown message: never leak raw backend English text into the UI.
  if (isUntranslatedEnglish(trimmed)) {
    return t('apiError.generic');
  }
  return trimmed;
}

/**
 * Extracts and translates the most relevant message from a DRF error body.
 * Mirrors the shape handled by `ApiError.extractMessage`, but every string
 * is routed through the translation map above instead of being shown as-is.
 */
export function getApiErrorMessage(body: ApiErrorBody | undefined, t: Translate): string | undefined {
  if (!body) return undefined;

  const pickValue = (): string[] | string | undefined => {
    if ('detail' in body && body.detail) return body.detail;
    const firstKey = Object.keys(body)[0];
    if (!firstKey) return undefined;
    return (body as Record<string, string[] | string>)[firstKey];
  };

  const value = pickValue();
  if (!value) return undefined;

  if (Array.isArray(value)) {
    return value.map((m) => translateOne(m, t)).join(' ');
  }
  return translateOne(value, t);
}

/**
 * Splits a DRF validation body into per-field messages plus a general message,
 * so forms can show each error under its own input (e.g. a duplicate username
 * under the username field and a duplicate email under the email field).
 */
export function getApiFieldErrors(
  body: ApiErrorBody | undefined,
  t: Translate,
): { fields: Record<string, string>; general?: string } {
  const fields: Record<string, string> = {};
  if (!body) return { fields };

  const generalParts: string[] = [];
  for (const [key, value] of Object.entries(body as Record<string, string[] | string>)) {
    if (!value || (Array.isArray(value) && value.length === 0)) continue;
    const messages = Array.isArray(value) ? value : [value];
    const text = messages.map((m) => translateOne(String(m), t)).join(' ');
    if (key === 'detail' || key === 'error' || key === 'non_field_errors') {
      generalParts.push(text);
    } else {
      fields[key] = text;
    }
  }
  return { fields, general: generalParts.length ? generalParts.join(' ') : undefined };
}
