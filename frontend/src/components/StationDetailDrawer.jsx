import React, { useState, useEffect } from 'react';
import {
  X,
  Calendar,
  CloudRain,
  Activity,
  BarChart2,
  AlertTriangle,
  MapPin,
  Compass,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import { formatProbability, formatDateIndo } from '../utils/formatters';
import RainfallObservationSummary from './RainfallObservationSummary';
import StationSpiTrendChart from './StationSpiTrendChart';

export default function StationDetailDrawer({
  stationId,
  periodId = '2026-09-das2',
  onClose,
}) {
  const [detail, setDetail] = useState(null);
  const [rainfallHistory, setRainfallHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rainfallLoading, setRainfallLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('current'); // 'current' | 'stats'

  useEffect(() => {
    if (!stationId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);
    setRainfallHistory(null);
    setActiveTab('current');

    // 1. Fetch Station Detail (Includes nearest_stations)
    authFetch(API_ENDPOINTS.STATION_DETAIL(stationId, periodId))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat data stasiun`);
        return res.json();
      })
      .then((data) => {
        if (isMounted) {
          setDetail(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Gagal terhubung ke backend API.');
          setLoading(false);
        }
      });

    // 2. Fetch Station Rainfall History (Default 15 days ending at cutoff)
    setRainfallLoading(true);
    authFetch(API_ENDPOINTS.STATION_RAINFALL_HISTORY(stationId, periodId, { days: 15 }))
      .then((res) => (res.ok ? res.json() : null))
      .then((rJson) => {
        if (isMounted) {
          setRainfallHistory(rJson);
          setRainfallLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setRainfallLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [stationId, periodId]);

  const handleApplyRange = (startDate, endDate) => {
    if (!stationId) return;
    setRainfallLoading(true);
    authFetch(API_ENDPOINTS.STATION_RAINFALL_HISTORY(stationId, periodId, { start_date: startDate, end_date: endDate }))
      .then((res) => (res.ok ? res.json() : null))
      .then((rJson) => {
        setRainfallHistory(rJson);
        setRainfallLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch custom rainfall history:', err);
        setRainfallLoading(false);
      });
  };

  const handleResetRange = () => {
    if (!stationId) return;
    setRainfallLoading(true);
    authFetch(API_ENDPOINTS.STATION_RAINFALL_HISTORY(stationId, periodId, { days: 15 }))
      .then((res) => (res.ok ? res.json() : null))
      .then((rJson) => {
        setRainfallHistory(rJson);
        setRainfallLoading(false);
      })
      .catch((err) => {
        console.error('Failed to reset rainfall history:', err);
        setRainfallLoading(false);
      });
  };

  if (!stationId) return null;

  const translateHazard = (h) => {
    if (!h) return 'NORMAL';
    const up = h.toUpperCase();
    if (up === 'DROUGHT') return 'Kekeringan Meteorologis';
    if (up === 'HEAVY_RAIN') return 'Curah Hujan Tinggi';
    if (up === 'MULTI_HAZARD') return 'Multi-Bahaya (Kekeringan & Curah Hujan Tinggi)';
    if (up === 'INCOMPLETE') return 'Evaluasi Belum Lengkap';
    if (up === 'NORMAL') return 'Tidak Ada Bahaya Aktif';
    return up;
  };

  const formatWib = (isoStr) => {
    if (!isoStr) return '-';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('id-ID', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short',
      });
    } catch {
      return isoStr;
    }
  };

  const formatCoord = (lat, lon) => {
    if (lat == null || lon == null) return '-';
    return `${parseFloat(lat).toFixed(4)}°, ${parseFloat(lon).toFixed(4)}°`;
  };

  const dasarianLabel = detail?.target_warning_period || 'Dasarian II Sep';

  return (
    <aside className="detail-drawer">
      {/* Drawer Header */}
      <div className="drawer-header">
        <div className="drawer-header-info">
          <div className="drawer-id-row">
            <span className="badge-station-id font-mono">{stationId}</span>
            {detail && (
              <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                  detail.pdkm_status === 'AWAS' ? 'bg-red-100 text-red-900 border-red-300 font-extrabold' :
                  detail.pdkm_status === 'SIAGA' ? 'bg-orange-100 text-orange-900 border-orange-300 font-extrabold' :
                  detail.pdkm_status === 'WASPADA' ? 'bg-amber-100 text-amber-900 border-amber-300 font-extrabold' :
                  detail.pdkm_status === 'INCOMPLETE' ? 'bg-slate-100 text-slate-700 border-slate-300' :
                  'bg-emerald-50 text-emerald-800 border-emerald-300'
                }`}>
                  PDKM: {detail.pdkm_status || 'NORMAL'}
                </span>
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                  detail.pdcht_status === 'AWAS' ? 'bg-red-100 text-red-900 border-red-300 font-extrabold' :
                  detail.pdcht_status === 'SIAGA' ? 'bg-orange-100 text-orange-900 border-orange-300 font-extrabold' :
                  detail.pdcht_status === 'WASPADA' ? 'bg-blue-100 text-blue-900 border-blue-300 font-extrabold' :
                  detail.pdcht_status === 'INCOMPLETE' ? 'bg-slate-100 text-slate-700 border-slate-300' :
                  'bg-emerald-50 text-emerald-800 border-emerald-300'
                }`}>
                  PDCHT: {detail.pdcht_status || 'NORMAL'}
                </span>
              </div>
            )}
          </div>
          <h2 className="drawer-title">{detail ? detail.station_name : 'Memuat Stasiun...'}</h2>
          <p className="drawer-subtitle">
            <MapPin size={12} className="inline-icon" />
            {detail ? `${detail.kabupaten}, ${detail.province || 'Kepulauan Riau'}` : ''}
          </p>
        </div>

        <button className="btn-close-drawer" onClick={onClose} title="Tutup panel detail">
          <X size={18} />
        </button>
      </div>

      {/* Drawer Tabs: Tab 1 (Status Operasional) & Tab 2 (Ringkasan Statistik) */}
      <div className="drawer-tabs">
        <button
          className={`drawer-tab ${activeTab === 'current' ? 'active' : ''}`}
          onClick={() => setActiveTab('current')}
        >
          <Activity size={14} />
          <span>Status Operasional</span>
        </button>
        <button
          className={`drawer-tab ${activeTab === 'stats' ? 'active' : ''}`}
          onClick={() => setActiveTab('stats')}
        >
          <BarChart2 size={14} />
          <span>Ringkasan Statistik</span>
        </button>
      </div>

      {/* Drawer Body */}
      <div className="drawer-body">
        {loading && (
          <div className="drawer-state-msg">
            <div className="spin spinner-lg"></div>
            <p>Memuat detail stasiun...</p>
          </div>
        )}

        {error && (
          <div className="drawer-state-msg error">
            <AlertTriangle size={28} className="text-red" />
            <p className="error-title">Gagal Memuat Data</p>
            <p className="error-desc">{error}</p>
          </div>
        )}

        {/* Tab 1: Status Operasional (termasuk Konteks Pos Terdekat) */}
        {!loading && !error && detail && activeTab === 'current' && (
          <div className="drawer-sections-flow">
            {/* 1. Status Overview Banner */}
            <div className={`status-hero-card ${detail.evaluation_status === 'INCOMPLETE' ? 'level-border-incomplete' : `level-border-${detail.warning_level.toLowerCase()}`}`}>
              <div className="hero-status-row">
                <div>
                  <span className="hero-k">Status Peringatan Aktual</span>
                  <div className={`hero-status-tag ${detail.evaluation_status === 'INCOMPLETE' ? 'tag-incomplete' : `tag-${detail.warning_level.toLowerCase()}`}`}>
                    {detail.evaluation_status === 'INCOMPLETE' ? 'EVALUASI TIDAK LENGKAP' : detail.warning_level}
                  </div>
                </div>
                <div className="text-right">
                  <span className="hero-k">Tipe Bahaya</span>
                  <div className="hero-hazard-tag">
                    {detail.evaluation_status === 'INCOMPLETE' ? 'DATA PARSIAL' : translateHazard(detail.hazard_type)}
                  </div>
                </div>
              </div>

              {/* Geographical Coordinates */}
              <div className="hero-geo-row">
                <span className="geo-item">
                  <strong>Koordinat:</strong> {formatCoord(detail.latitude, detail.longitude)}
                </span>
                {detail.elevation_m != null && (
                  <span className="geo-item">
                    <strong>Elevasi:</strong> {detail.elevation_m} m dpl
                  </span>
                )}
                <span className="geo-item">
                  <strong>ZOM:</strong> {String(detail.station_id || '').trim().toLowerCase() === '21050101a' ? 'Belum terpetakan / Tidak masuk poligon ZOM' : (detail.nozom_prov ? `ZOM ${detail.nozom_prov}` : 'Tidak tersedia')}
                </span>

              </div>
            </div>



            {/* 2. Metadata Periode */}
            <div className="drawer-card">
              <h3 className="section-heading">
                <Calendar size={15} />
                <span>Informasi Periode</span>
              </h3>
              <div className="info-keyvalue-list">
                <div className="info-kv-row">
                  <span className="info-k">Periode Peringatan Dini:</span>
                  <span className="info-v bold">{detail.target_warning_period}</span>
                </div>
                <div className="info-kv-row">
                  <span className="info-k">Cutoff Observasi HTH:</span>
                  <span className="info-v font-mono">{detail.last_observation_date || '2026-09-20'}</span>
                </div>
                {(detail.prev_dasarian_rainfall_mm != null || detail.ch_dasarian_2_mm != null) && (
                  <div className="info-kv-row">
                    <span className="info-k">{detail.prev_dasarian_label || 'CH Dasarian Sebelumnya'}:</span>
                    <span className="info-v font-mono">{(detail.prev_dasarian_rainfall_mm ?? detail.ch_dasarian_2_mm).toFixed(1)} mm</span>
                  </div>
                )}
                <div className="info-kv-row">
                  <span className="info-k">Waktu Pemrosesan Sistem:</span>
                  <span className="info-v font-mono text-xs">{formatWib(detail.updated_at)}</span>
                </div>
              </div>
            </div>

            {/* 3. Evaluasi Dual Hazard Terpadu (PDKM & PDCHT) */}
            <div className="drawer-card">
              <h3 className="section-heading mb-3 flex items-center space-x-2">
                <CloudRain size={16} />
                <span>Evaluasi Dual Hazard (PDKM & PDCHT)</span>
              </h3>

              {/* Group A: PDKM */}
              <div className="p-3 mb-3 rounded-lg border border-amber-200 bg-amber-50/40">
                <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-amber-200">
                  <div className="flex items-center space-x-1.5">
                    <span className="text-amber-600 font-bold">☀️</span>
                    <strong className="text-xs font-bold text-amber-900">A. PDKM — KEKERINGAN METEOROLOGIS</strong>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                    detail.pdkm_status === 'AWAS' ? 'bg-red-600 text-white' :
                    detail.pdkm_status === 'SIAGA' ? 'bg-orange-500 text-white' :
                    detail.pdkm_status === 'WASPADA' ? 'bg-amber-400 text-slate-900' :
                    detail.pdkm_status === 'INCOMPLETE' ? 'bg-slate-200 text-slate-700' :
                    'bg-emerald-600 text-white'
                  }`}>
                    {detail.pdkm_status || 'NORMAL'}
                  </span>
                </div>

                <ul className="text-xs space-y-1.5 text-slate-700 list-disc list-inside">
                  <li>
                    <span className="font-semibold">Hari Tanpa Hujan (HTH):</span>{' '}
                    <span className="font-mono font-bold">{detail.hth_days_current != null ? `${detail.hth_days_current} hari` : 'Tidak tersedia'}</span>{' '}
                    <span className="text-slate-500 text-[11px]">(Ambang: Waspada 21–30 hr, Siaga 31–60 hr, Awas &gt;60 hr)</span>
                  </li>
                  <li>
                    <span className="font-semibold">SPI 90D (Parameter Utama PDKM):</span>{' '}
                    <span className="font-mono font-bold">
                      {detail.spi_value_90d != null ? detail.spi_value_90d.toFixed(2) : '—'}
                    </span>{' '}
                    <span className="text-slate-500 text-[11px]">(Ambang: Waspada ≤ -1.00, Siaga ≤ -1.50, Awas ≤ -2.00)</span>
                  </li>
                  <li>
                    <span className="font-semibold">SPI 30D (Indikator Pendukung):</span>{' '}
                    <span className="font-mono font-bold">
                      {detail.spi_value != null ? detail.spi_value.toFixed(2) : '—'}
                    </span>{' '}
                    <span className="text-slate-500 text-[11px]">(Informasional kondisi jangka pendek)</span>
                  </li>
                  <li>
                    <span className="font-semibold">Peluang CH &lt; 20 mm (Pb20):</span>{' '}
                    <span className="font-mono font-bold">
                      {formatProbability(detail.prob_below20)}
                    </span>{' '}
                    <span className="text-slate-500 text-[11px]">(Ambang Pemicu: &gt; 70%)</span>
                  </li>
                  {detail.pdkm_reasons && (
                    <li className="text-amber-800 font-medium list-none pt-1">
                      📌 <span className="font-semibold">Indikator Pemicu:</span> {detail.pdkm_reasons}
                    </li>
                  )}
                </ul>
              </div>

              {/* Group B: PDCHT */}
              <div className="p-3 rounded-lg border border-blue-200 bg-blue-50/40">
                <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-blue-200">
                  <div className="flex items-center space-x-1.5">
                    <span className="text-blue-600 font-bold">🌧️</span>
                    <strong className="text-xs font-bold text-blue-900">B. PDCHT — CURAH HUJAN TINGGI</strong>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                    detail.pdcht_status === 'AWAS' ? 'bg-red-600 text-white' :
                    detail.pdcht_status === 'SIAGA' ? 'bg-orange-500 text-white' :
                    detail.pdcht_status === 'WASPADA' ? 'bg-blue-600 text-white' :
                    detail.pdcht_status === 'INCOMPLETE' ? 'bg-slate-200 text-slate-700' :
                    'bg-emerald-600 text-white'
                  }`}>
                    {detail.pdcht_status || 'NORMAL'}
                  </span>
                </div>

                <ul className="text-xs space-y-1.5 text-slate-700 list-disc list-inside">
                  <li>
                    <span className="font-semibold">Peluang CH Dasarian &gt; 150 mm (Pa150):</span>{' '}
                    <span className="font-mono font-bold">{formatProbability(detail.prob_above150)}</span>{' '}
                    <span className="text-slate-500 text-[11px]">(Waspada jika &gt; 50%)</span>
                  </li>
                  <li>
                    <span className="font-semibold">Peluang CH Dasarian &gt; 200 mm (Pa200):</span>{' '}
                    <span className="font-mono font-bold">{formatProbability(detail.prob_above200)}</span>{' '}
                    <span className="text-slate-500 text-[11px]">(Siaga jika &gt; 50%)</span>
                  </li>
                  <li>
                    <span className="font-semibold">Peluang CH Dasarian &gt; 300 mm (Pa300):</span>{' '}
                    <span className="font-mono font-bold">{formatProbability(detail.prob_above300)}</span>{' '}
                    <span className="text-slate-500 text-[11px]">(Awas jika &gt; 50%)</span>
                  </li>
                  <li>
                    <span className="font-semibold">Peluang CH Bulanan (&gt;300 / &gt;400 / &gt;500 mm):</span>{' '}
                    <span className="font-mono font-bold">
                      {(
                        `${formatProbability(detail.prob_month_above300 ?? detail.monthly_pa300, '-')} / ${formatProbability(detail.prob_month_above400 ?? detail.monthly_pa400, '-')} / ${formatProbability(detail.prob_month_above500 ?? detail.monthly_pa500, '-')}`
                      )}
                    </span>{' '}
                    <span className="text-slate-500 text-[11px]">(Waspada / Siaga / Awas jika &gt; 50%)</span>
                  </li>
                  {detail.pdcht_reasons && (
                    <li className="text-blue-800 font-medium list-none pt-1">
                      📌 <span className="font-semibold">Indikator Pemicu:</span> {detail.pdcht_reasons}
                    </li>
                  )}
                </ul>
              </div>
            </div>

            {/* 4. Konteks Pos Terdekat */}
            <div className="drawer-card">
              <div className="section-title-row mb-2">
                <div className="flex-align gap-2">
                  <Compass size={15} className="text-forest" />
                  <h3 className="section-heading mb-0">Konteks Pos Terdekat</h3>
                </div>
              </div>
              <p className="text-xs text-muted mb-3">
                Referensi spasial variabilitas lokal stasiun-stasiun terdekat di sekitarnya.
              </p>

              {detail.nearest_stations && detail.nearest_stations.length > 0 ? (
                <div className="table-responsive-wrapper">
                  <table className="drawer-nearest-table">
                    <thead>
                      <tr>
                        <th>Pos / Stasiun</th>
                        <th className="text-right">Jarak</th>
                        <th className="text-right">HTH</th>
                        <th className="text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.nearest_stations.map((n) => (
                        <tr key={n.station_id} className="nearest-row">
                          <td>
                            <div className="nearest-stn-name">{n.station_name}</div>
                            <div className="font-mono text-xs text-muted">
                              {n.station_id} &bull; {n.kabupaten}
                            </div>
                          </td>
                          <td className="text-right font-mono font-bold text-forest">
                            {n.distance_km} km
                          </td>
                          <td className="text-right font-mono font-bold">
                            {n.hth_days_current !== null ? `${n.hth_days_current} hr` : '-'}
                          </td>
                          <td className="text-center">
                            <span className={`badge-pill lvl-${n.warning_level.toLowerCase()}`}>
                              {n.warning_level}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-muted">Data stasiun terdekat tidak tersedia.</p>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Ringkasan Statistik */}
        {!loading && !error && detail && activeTab === 'stats' && (
          <div className="drawer-stats-tab-content drawer-sections-flow">
            {/* 1. Visualisasi Tren Indeks SPI Stasiun */}
            <StationSpiTrendChart stationId={stationId} defaultScale="DASARIAN" />

            {/* 2. Ringkasan Observasi Curah Hujan Harian */}
            <RainfallObservationSummary
              data={rainfallHistory?.data || []}
              periodStart={rainfallHistory?.period_start}
              periodEnd={rainfallHistory?.period_end}
              stationName={detail.station_name}
              stationId={detail.station_id}
              loading={rainfallLoading}
              error={rainfallHistory?.error}
              cutoffDate={detail.last_observation_date || '2026-09-20'}
              isCustomRange={Boolean(rainfallHistory?.is_custom_range)}
              onApplyRange={handleApplyRange}
              onResetRange={handleResetRange}
              showTableToggle={true}
            />
          </div>
        )}
      </div>
    </aside>
  );
}
