/**
 * Minimal Gregorian <-> Jalali (Shamsi) YEAR conversion.
 *
 * The vehicle "year" field only stores a bare manufacture year (no month/day),
 * so an exact calendar conversion isn't possible — Nowruz falls around March
 * 21, so a given Gregorian year overlaps two Jalali years. We use the
 * standard fixed offset of 621 years, which is correct for the large
 * majority of the year and is the conventional approximation used whenever
 * only a year (not a full date) is available.
 */
const JALALI_YEAR_OFFSET = 621;

/** Convert a Gregorian year to its (approximate) Jalali equivalent. */
export function gregorianYearToJalali(gregorianYear: number): number {
  return gregorianYear - JALALI_YEAR_OFFSET;
}

/** Convert a Jalali year back to its (approximate) Gregorian equivalent. */
export function jalaliYearToGregorian(jalaliYear: number): number {
  return jalaliYear + JALALI_YEAR_OFFSET;
}
