/**
 * Centralized formatting and normalization utilities for DSS-PIK
 * BMKG Stasiun Klimatologi Kepulauan Riau
 */

/**
 * Normalizes and formats a probability value to a percentage string.
 * Internal scale is 0–100.
 *
 * Rules:
 * - null / undefined / NaN / '' -> fallback ('Tidak tersedia')
 * - 0 -> '0%'
 * - 1 -> '1%' (1 ensemble member out of 51)
 * - 96 -> '96%'
 * - 0.96 -> '96%' (if fractional scale is passed)
 * - 100 -> '100%'
 * - Values are never multiplied by 100 if they are already >= 1.0!
 *
 * @param {number|string|null} val - Raw probability value
 * @param {string} fallback - String to return if missing
 * @returns {string} - Formatted percentage e.g. '96%'
 */
export function formatProbability(val, fallback = 'Tidak tersedia') {
  if (val === null || val === undefined || val === '') return fallback;
  const num = typeof val === 'number' ? val : parseFloat(val);
  if (isNaN(num)) return fallback;

  let pct = num;
  // If the value is strictly between 0 and 1 (exclusive, e.g. 0.96 or 0.05),
  // it is in 0..1 scale, so convert to 0..100.
  // Note: 0 is 0%, 1 is 1% (in ECMWF 51 ensemble members).
  if (num > 0 && num < 1.0) {
    pct = num * 100;
  }

  // Format cleanly without trailing .0 if integer
  const rounded = Number(pct.toFixed(1));
  const text = rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(1);
  return `${text}%`;
}

/**
 * Format rainfall in mm
 */
export function formatRainfall(val, fallback = '-') {
  if (val === null || val === undefined || val === '') return fallback;
  const num = typeof val === 'number' ? val : parseFloat(val);
  if (isNaN(num)) return fallback;
  return `${num.toFixed(1)} mm`;
}

/**
 * Format Indonesian date
 */
export function formatDateIndo(dateStr) {
  if (!dateStr) return '-';
  try {
    const parts = dateStr.split('-');
    if (parts.length === 3) {
      const months = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
      return `${parseInt(parts[2], 10)} ${months[parseInt(parts[1], 10) - 1]} ${parts[0]}`;
    }
    return dateStr;
  } catch {
    return dateStr;
  }
}
