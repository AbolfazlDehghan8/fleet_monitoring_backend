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
  license_number: 'apiError.field.license_number',
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
];

function fieldLabel(field: string, t: Translate): string {
  const key = FIELD_LABEL_KEYS[field];
  return key ? t(key) : field;
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
