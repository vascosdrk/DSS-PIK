/**
 * CEWS Frontend Configuration
 * Supports:
 * 1. Explicit VITE_API_BASE_URL from environment (ignored if it points to 127.0.0.1/localhost while browser is on a LAN IP)
 * 2. Vite dev server (port 5173) -> http://<hostname>:8000
 * 3. Production / LAN Server (:8000) / HTTPS Reverse Proxy -> same-origin ('')
 */
const resolveApiBaseUrl = () => {
  const envUrl = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '');
  if (typeof window !== 'undefined' && window.location) {
    const host = window.location.hostname;
    const isLocalBrowser = host === 'localhost' || host === '127.0.0.1';
    const envIsLocalOnly = envUrl.includes('127.0.0.1') || envUrl.includes('localhost');

    if (envUrl && !(envIsLocalOnly && !isLocalBrowser)) {
      return envUrl;
    }
    if (window.location.port === '5173') {
      return `http://${host}:8000`;
    }
    return '';
  }
  return envUrl || 'http://127.0.0.1:8000';
};

export const API_BASE_URL = resolveApiBaseUrl();

/**
 * Single Source of Truth for DSS-PIK Institutional Identity (Frontend)
 */
export const INSTITUTION_NAME =
  'BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang';
export const INSTITUTION_SHORT_NAME =
  'Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang';

export const TOKEN_STORAGE_KEY = 'dss_pik_auth_token';

export function getStoredAuthToken() {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(TOKEN_STORAGE_KEY) || localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredAuthToken(token) {
  if (typeof window === 'undefined') return;
  if (token) {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export function getAuthHeaders(headers = {}) {
  const merged = { ...headers };
  const token = getStoredAuthToken();
  if (token) {
    merged['Authorization'] = `Bearer ${token}`;
  }
  return merged;
}

/**
 * Standardized fetch wrapper providing:
 * 1. credentials: 'include' (for signed HttpOnly cookies)
 * 2. Authorization: Bearer <token> (for cross-site / cookie-fallback resilience)
 */
export async function authFetch(url, options = {}) {
  const finalOptions = {
    ...options,
    credentials: 'include',
    headers: getAuthHeaders(options.headers || {}),
  };
  return fetch(url, finalOptions);
}

export const API_ENDPOINTS = {
  HEALTH: `${API_BASE_URL}/health`,
  LOGIN: `${API_BASE_URL}/api/v1/auth/login`,
  LOGOUT: `${API_BASE_URL}/api/v1/auth/logout`,
  AUTH_ME: `${API_BASE_URL}/api/v1/auth/me`,
  PERIODS: `${API_BASE_URL}/api/v1/periods`,
  CURRENT_WARNING: (periodId) => `${API_BASE_URL}/api/v1/current-warning${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''}`,
  HTH_TABLE: (periodId) => `${API_BASE_URL}/api/v1/hth${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''}`,
  EARLY_WARNING_TABLE: (periodId) => `${API_BASE_URL}/api/v1/early-warning-table${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''}`,
  STATION_DETAIL: (stationId, periodId) =>
    `${API_BASE_URL}/api/v1/stations/${encodeURIComponent(stationId)}/detail${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''}`,
  STATION_HISTORY: (stationId) =>
    `${API_BASE_URL}/api/v1/stations/${encodeURIComponent(stationId)}/history`,
  STATION_EVALUATION: (stationId, periodId) =>
    `${API_BASE_URL}/api/v1/stations/${encodeURIComponent(stationId)}/evaluation${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''}`,
  STATION_RAINFALL_HISTORY: (stationId, periodId, params = {}) => {
    const q = new URLSearchParams();
    if (periodId) q.append('period_id', periodId);
    if (params.days) q.append('days', params.days);
    if (params.start_date) q.append('start_date', params.start_date);
    if (params.end_date) q.append('end_date', params.end_date);
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/stations/${encodeURIComponent(stationId)}/rainfall-history${qs ? `?${qs}` : ''}`;
  },
  RAINFALL_COLUMNS: `${API_BASE_URL}/api/v1/rainfall/columns`,
  RAINFALL_DAILY_TABLE: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        q.append(k, v);
      }
    });
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/rainfall/daily-table${qs ? `?${qs}` : ''}`;
  },
  STATIONS_MASTER: `${API_BASE_URL}/api/v1/stations/master`,
  RAINFALL_INPUT_STATIONS: `${API_BASE_URL}/api/v1/stations/master`,
  RAINFALL_INPUT_CURRENT_VALUES: (startDate, endDate) =>
    `${API_BASE_URL}/api/v1/rainfall/input/current-values?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
  RAINFALL_INPUT_PREVIEW: `${API_BASE_URL}/api/v1/rainfall/input/validate-preview`,
  RAINFALL_INPUT_COMMIT: `${API_BASE_URL}/api/v1/rainfall/input/commit`,

  // DSS-PIK Data Center & Download Endpoints
  STATION_INFO: (stationId) =>
    `${API_BASE_URL}/api/v1/stations/${encodeURIComponent(stationId)}/info`,
  SPI_DATA: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/spi/data${qs ? `?${qs}` : ''}`;
  },
  SPI_DOWNLOAD: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/spi/download${qs ? `?${qs}` : ''}`;
  },
  PROBABILITY_PERIODS: `${API_BASE_URL}/api/v1/probability/periods`,
  PROBABILITY_DATA: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/probability/data${qs ? `?${qs}` : ''}`;
  },
  PROBABILITY_DOWNLOAD: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/probability/download${qs ? `?${qs}` : ''}`;
  },
  RAINFALL_DOWNLOAD: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/rainfall/download${qs ? `?${qs}` : ''}`;
  },

  // Operational Warnings Refresh & Evaluate
  WARNINGS_REFRESH_EVALUATE: (periodId) => `${API_BASE_URL}/api/v1/warnings/refresh-evaluate${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''}`,

  // Operational Period Readiness & Map Generation
  PERIOD_SELECT: `${API_BASE_URL}/api/v1/periods/select`,
  PERIOD_READINESS: (periodId) => `${API_BASE_URL}/api/v1/periods/readiness${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''}`,
  MAP_GENERATE: `${API_BASE_URL}/api/v1/maps/generate`,
  MAP_GENERATE_JSON: `${API_BASE_URL}/api/v1/maps/generate-json`,
  MAP_DOWNLOAD: (filename) => `${API_BASE_URL}/api/v1/maps/download/${encodeURIComponent(filename)}`,
  MAP_HISTORY: `${API_BASE_URL}/api/v1/maps/history`,
  GEO_LAYER: (layerName) => `${API_BASE_URL}/api/v1/geo/layers/${encodeURIComponent(layerName)}`,
  GEO_ZOM_ANALYSIS: (periodId) => `${API_BASE_URL}/api/v1/geo/zom-analysis${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''}`,

  // SPI Generator Endpoints
  SPI_GENERATOR_OPTIONS: `${API_BASE_URL}/api/v1/spi/generator/options`,
  SPI_GENERATOR_PREVIEW: `${API_BASE_URL}/api/v1/spi/generator/preview`,
  SPI_GENERATOR_EXECUTE: `${API_BASE_URL}/api/v1/spi/generator/execute`,
  SPI_GENERATOR_COMMIT: `${API_BASE_URL}/api/v1/spi/generator/commit`,

  // Operational Ingestion & Multi-Scale SPI Trend
  STATION_SPI_TREND: (stationId, months = 12) =>
    `${API_BASE_URL}/api/v1/stations/${encodeURIComponent(stationId)}/spi-trend?months=${months}`,
  INGESTION_PREVIEW: `${API_BASE_URL}/api/v1/ingestion/preview`,
  INGESTION_COMMIT: `${API_BASE_URL}/api/v1/ingestion/commit`,
  INGESTION_HISTORY: (limit = 20) =>
    `${API_BASE_URL}/api/v1/ingestion/history?limit=${limit}`,
  INGESTION_LATEST_STATUS: `${API_BASE_URL}/api/v1/ingestion/latest-status`,
  INGESTION_OPERATIONAL_SUMMARY: `${API_BASE_URL}/api/v1/ingestion/operational-summary`,
  INGESTION_BATCHES: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/ingestion/batches${qs ? `?${qs}` : ''}`;
  },
  INGESTION_BATCH_DETAIL: (batchId) =>
    `${API_BASE_URL}/api/v1/ingestion/batch/${encodeURIComponent(batchId)}`,
  INGESTION_BATCH_CANCEL: (batchId) =>
    `${API_BASE_URL}/api/v1/ingestion/batch/${encodeURIComponent(batchId)}/cancel`,
  INGESTION_RECORD_CORRECT: `${API_BASE_URL}/api/v1/ingestion/record/correct`,
  INGESTION_RECORD_VOID: `${API_BASE_URL}/api/v1/ingestion/record/void`,
  INGESTION_SPI_VOID: `${API_BASE_URL}/api/v1/ingestion/spi/void`,
  INGESTION_PROBABILITY_VOID: `${API_BASE_URL}/api/v1/ingestion/probability/void`,
  INGESTION_CORRECTIONS_LOG: (limit = 100) =>
    `${API_BASE_URL}/api/v1/ingestion/corrections-log?limit=${limit}`,
  FORECAST_VINTAGES: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/forecast/vintages${qs ? `?${qs}` : ''}`;
  },

  // Regional Warning Management & SIH3 Publication Endpoints
  REGIONAL_WARNINGS_MAPPING: `${API_BASE_URL}/api/v1/warnings/regional/mapping`,
  REGIONAL_WARNINGS_RECOMMENDATIONS: (periodId, minCoveragePct = 50.0) => {
    const q = new URLSearchParams();
    if (periodId) q.append('period_id', periodId);
    if (minCoveragePct !== undefined && minCoveragePct !== null) q.append('min_coverage_pct', minCoveragePct);
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/warnings/regional/recommendations${qs ? `?${qs}` : ''}`;
  },
  KECAMATAN_WARNINGS_RECOMMENDATIONS: (periodId, minCoveragePct = 50.0) => {
    const q = new URLSearchParams();
    if (periodId) q.append('period_id', periodId);
    if (minCoveragePct !== undefined && minCoveragePct !== null) q.append('min_coverage_pct', minCoveragePct);
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/warnings/kecamatan/recommendations${qs ? `?${qs}` : ''}`;
  },
  REGIONAL_WARNINGS_DECISIONS: (periodId, regionCode) => {
    const q = new URLSearchParams();
    if (periodId) q.append('period_id', periodId);
    if (regionCode) q.append('region_code', regionCode);
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/warnings/regional/decisions${qs ? `?${qs}` : ''}`;
  },
  REGIONAL_WARNING_DETAIL: (regionCode, periodId) => {
    const q = new URLSearchParams();
    if (periodId) q.append('period_id', periodId);
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/warnings/regional/${encodeURIComponent(regionCode)}${qs ? `?${qs}` : ''}`;
  },
  REGIONAL_WARNING_DECISION_SAVE: `${API_BASE_URL}/api/v1/warnings/regional/decision`,
  REGIONAL_WARNINGS_BULK_INIT: `${API_BASE_URL}/api/v1/warnings/regional/decisions/bulk-init`,
  SIH3_PUBLICATION_PREVIEW: `${API_BASE_URL}/api/v1/publications/sih3/preview`,
  SIH3_PUBLICATION_VALIDATE: `${API_BASE_URL}/api/v1/publications/sih3/validate`,
  SIH3_PUBLICATION_WORKFLOW: `${API_BASE_URL}/api/v1/publications/sih3/workflow`,
  SIH3_PUBLICATION_PUBLISH: `${API_BASE_URL}/api/v1/publications/sih3/publish`,
  SIH3_PUBLICATION_HISTORY: (periodId, limit = 50) => {
    const q = new URLSearchParams();
    if (periodId) q.append('period_id', periodId);
    if (limit) q.append('limit', limit);
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/publications/sih3/history${qs ? `?${qs}` : ''}`;
  },
  SIH3_PUBLICATION_LATEST_JSON: (periodId) => {
    const q = new URLSearchParams();
    if (periodId) q.append('period_id', periodId);
    const qs = q.toString();
    return `${API_BASE_URL}/api/v1/publications/sih3/latest.json${qs ? `?${qs}` : ''}`;
  },
  SIH3_PUBLICATION_JSON_BY_ID: (publicationId) =>
    `${API_BASE_URL}/api/v1/publications/sih3/${encodeURIComponent(publicationId)}/json`,

  // Rainfall Input Module V2 (Auto Template Detection, Multi-Format & Manual)
  RAINFALL_V2_REGENCIES: `${API_BASE_URL}/api/v1/rainfall/v2/regencies`,
  RAINFALL_V2_DETECT: `${API_BASE_URL}/api/v1/rainfall/v2/detect`,
  RAINFALL_V2_PROFILES: `${API_BASE_URL}/api/v1/rainfall/v2/profiles`,
  RAINFALL_V2_PREVIEW: `${API_BASE_URL}/api/v1/rainfall/v2/preview`,
  RAINFALL_V2_COMMIT: `${API_BASE_URL}/api/v1/rainfall/v2/commit`,
  RAINFALL_V2_MANUAL_PREVIEW: `${API_BASE_URL}/api/v1/rainfall/v2/manual/preview`,
  RAINFALL_V2_MANUAL_COMMIT: `${API_BASE_URL}/api/v1/rainfall/v2/manual/commit`,
  RAINFALL_V2_DELETE_PREVIEW: `${API_BASE_URL}/api/v1/rainfall/v2/delete/preview`,
  RAINFALL_V2_DELETE_COMMIT: `${API_BASE_URL}/api/v1/rainfall/v2/delete/commit`,
};

