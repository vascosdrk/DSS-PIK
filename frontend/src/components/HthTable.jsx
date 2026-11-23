import React, { useState, useMemo, useEffect } from 'react';
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  CloudRain,
  Droplets,
  Sun,
  Loader2,
  Filter,
  Info,
  Layers,
  Radio,
  HelpCircle,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import RainfallObservationSummary from './RainfallObservationSummary';

export default function HthTable({
  stations = [],
  selectedStationId,
  onSelectStation,
  onOpenEvaluation,
  evaluatedStatusMap = {},
  prevDasarianLabel = 'CH Dasarian Sebelumnya (mm)',
  periodId = '2026-09-das2',
}) {
  const [sortField, setSortField] = useState('warning_priority');
  const [sortOrder, setSortOrder] = useState('desc'); // 'asc' or 'desc'

  // Expandable rainfall history state
  const [expandedStationId, setExpandedStationId] = useState(null);
  const [rainfallHistoryCache, setRainfallHistoryCache] = useState({});
  const [rainfallLoadingMap, setRainfallLoadingMap] = useState({});

  // Reset expanded row and cache when period changes
  useEffect(() => {
    setExpandedStationId(null);
    setRainfallHistoryCache({});
  }, [periodId]);

  const translateHazard = (h) => {
    if (!h) return null;
    const up = h.toUpperCase();
    if (up === 'DROUGHT') return 'Kekeringan';
    if (up === 'HEAVY_RAIN') return 'Hujan Lebat';
    return null;
  };

  const formatDate = (d) => {
    if (!d) return '—';
    try {
      const parts = d.split('-');
      if (parts.length === 3) {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
        return `${parseInt(parts[2], 10)} ${months[parseInt(parts[1], 10) - 1]} ${parts[0]}`;
      }
      return d;
    } catch {
      return d;
    }
  };

  // Format probabilities cleanly to 0–100% scale
  // Returns '—' for null/undefined or ARG stations
  const formatProb = (val, isArg = false) => {
    if (isArg || val === undefined || val === null) return '—';
    const num = Number(val);
    if (isNaN(num)) return '—';
    // Round to 1 decimal place or whole number
    return `${Number(num.toFixed(1))}%`;
  };

  // Warning level priority score for deterministic sorting
  const getWarningPriority = (stn) => {
    const raw = (stn.warning_level || 'NORMAL').toUpperCase();
    if (stn.evaluation_status === 'INCOMPLETE' || raw === 'INCOMPLETE') return 0;
    if (raw.includes('AWAS')) return 4;
    if (raw.includes('SIAGA')) return 3;
    if (raw.includes('WASPADA')) return 2;
    if (raw.includes('AMAN') || raw.includes('NORMAL')) return 1;
    return 0;
  };

  // Sorting (stations are already filtered by global FilterBar at the dashboard level)
  const sortedStations = useMemo(() => {
    const list = Array.isArray(stations) ? [...stations] : [];
    list.sort((a, b) => {
      let valA, valB;

      if (sortField === 'warning_priority') {
        valA = getWarningPriority(a);
        valB = getWarningPriority(b);
        if (valA !== valB) {
          return sortOrder === 'asc' ? valA - valB : valB - valA;
        }
        // Secondary sort: HTH days
        const hthA = a.hth_days_current ?? -1;
        const hthB = b.hth_days_current ?? -1;
        return sortOrder === 'asc' ? hthA - hthB : hthB - hthA;
      }

      valA = a[sortField];
      valB = b[sortField];

      // Handle nulls: keep nulls at the bottom
      if (valA === undefined || valA === null) return 1;
      if (valB === undefined || valB === null) return -1;

      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortOrder === 'asc' ? valA - valB : valB - valA;
      }

      valA = String(valA).toLowerCase();
      valB = String(valB).toLowerCase();
      if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
      if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
    return list;
  }, [stations, sortField, sortOrder]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder(['hth_days_current', 'warning_priority', 'pdkm_level', 'pdcht_level', 'prob_below20', 'prev_dasarian_rainfall_mm'].includes(field) ? 'desc' : 'asc');
    }
  };

  const renderSortIcon = (field) => {
    if (sortField !== field) return <ArrowUpDown size={12} className="sort-icon-muted" />;
    return sortOrder === 'asc' ? <ArrowUp size={12} className="sort-icon-active" /> : <ArrowDown size={12} className="sort-icon-active" />;
  };

  // Toggle expandable daily rainfall history
  const handleToggleRainfall = async (e, station) => {
    e.stopPropagation();
    const sid = station.station_id;

    if (expandedStationId === sid) {
      setExpandedStationId(null);
      return;
    }

    setExpandedStationId(sid);

    if (rainfallHistoryCache[sid]) {
      return;
    }

    setRainfallLoadingMap((prev) => ({ ...prev, [sid]: true }));
    try {
      const res = await authFetch(API_ENDPOINTS.STATION_RAINFALL_HISTORY(sid, periodId));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRainfallHistoryCache((prev) => ({ ...prev, [sid]: data }));
    } catch (err) {
      console.warn('Failed to load rainfall history for', sid, err);
      setRainfallHistoryCache((prev) => ({
        ...prev,
        [sid]: { error: 'Data curah hujan harian tidak dapat dimuat.' },
      }));
    } finally {
      setRainfallLoadingMap((prev) => ({ ...prev, [sid]: false }));
    }
  };

  return (
    <div className="early-warning-table-wrapper">
      {/* 1. Header Toolbar */}
      <div className="table-header-toolbar">
        <div className="toolbar-left">
          <div className="table-title-group">
            <h3 className="table-main-heading">Tabel Peringatan Dini</h3>
            <span className="table-badge-count">{sortedStations.length} Stasiun</span>
          </div>
          <p className="table-subheading">
            Ringkasan status peringatan iklim, HTH aktual, SPI 30-hari, dan probabilitas curah hujan periode aktif
          </p>
        </div>
      </div>

      {/* 2. Structured Table with Sticky Headers & Sticky First Column */}
      <div className="table-scroll-container">
        <table className="early-warning-table">
          <thead>
            {/* Top Multi-Header Row for Grouped Indicators */}
            <tr className="th-group-row">
              <th colSpan={3} className="th-group-ident">IDENTITAS STASIUN</th>
              <th colSpan={4} className="th-group-status">STATUS & INDIKATOR OBSERVASI</th>
              <th colSpan={4} className="th-group-dasarian">
                PROBABILITAS CH DASARIAN
                <span className="th-sub-note">(Skala 0–100%)</span>
              </th>
              <th colSpan={3} className="th-group-bulanan">
                CH BULANAN
                <span className="th-sub-note">(Peluang Akumulasi)</span>
              </th>
              <th colSpan={2} className="th-group-eval">EVALUASI & AKSI</th>
            </tr>

            {/* Column Headers Row */}
            <tr className="th-columns-row">
              {/* 1. Nama & ID Stasiun (Sticky) */}
              <th
                onClick={() => handleSort('station_name')}
                className="cursor-pointer th-sticky-col"
                style={{ minWidth: '220px' }}
                title="Nama dan ID stasiun master"
              >
                <div className="th-flex">
                  <span>NAMA & ID STASIUN</span>
                  {renderSortIcon('station_name')}
                </div>
              </th>

              {/* 2. Kabupaten / Kota */}
              <th
                onClick={() => handleSort('kabupaten')}
                className="cursor-pointer"
                style={{ minWidth: '130px' }}
                title="Kabupaten / Kota wilayah stasiun"
              >
                <div className="th-flex">
                  <span>KABUPATEN/KOTA</span>
                  {renderSortIcon('kabupaten')}
                </div>
              </th>

              {/* 3. Jenis Stasiun */}
              <th
                onClick={() => handleSort('is_arg')}
                className="cursor-pointer text-center"
                style={{ width: '110px' }}
                title="Cakupan Stasiun Pengamatan"
              >
                <div className="th-flex justify-center">
                  <span>JENIS</span>
                  {renderSortIcon('is_arg')}
                </div>
              </th>

              {/* 4. PDKM Status (Kekeringan Meteorologis) */}
              <th
                onClick={() => handleSort('pdkm_level')}
                className="cursor-pointer text-center bg-amber-50/70 text-amber-950 border-amber-200"
                style={{ minWidth: '125px' }}
                title="Status Peringatan Dini Kekeringan Meteorologis (HTH, SPI 30D, Pb20)"
              >
                <div className="th-flex justify-center text-amber-900 font-bold">
                  <span>STATUS PDKM</span>
                  {renderSortIcon('pdkm_level')}
                </div>
              </th>

              {/* 5. PDCHT Status (Curah Hujan Tinggi) */}
              <th
                onClick={() => handleSort('pdcht_level')}
                className="cursor-pointer text-center bg-blue-50/70 text-blue-950 border-blue-200"
                style={{ minWidth: '125px' }}
                title="Status Peringatan Dini Curah Hujan Tinggi (Probabilitas Dasarian & Bulanan)"
              >
                <div className="th-flex justify-center text-blue-900 font-bold">
                  <span>STATUS PDCHT</span>
                  {renderSortIcon('pdcht_level')}
                </div>
              </th>

              {/* 5. HTH Aktual */}
              <th
                onClick={() => handleSort('hth_days_current')}
                className="cursor-pointer text-right"
                style={{ minWidth: '130px' }}
                title="Hari Tanpa Hujan aktual sampai tanggal cutoff observasi"
              >
                <div className="th-flex justify-end">
                  <span>HTH AKTUAL</span>
                  {renderSortIcon('hth_days_current')}
                </div>
              </th>

              {/* 6. SPI Dasarian 30D */}
              <th
                onClick={() => handleSort('spi_value')}
                className="cursor-pointer text-right"
                style={{ width: '105px' }}
                title="SPI Dasarian 30D: Akumulasi 30 hari (3 dasarian) — Indikator pemicu Decision Engine"
              >
                <div className="th-flex justify-end">
                  <span>SPI 30D</span>
                  {renderSortIcon('spi_value')}
                </div>
              </th>

              {/* 7. SPI Dasarian 90D */}
              <th
                onClick={() => handleSort('spi_value_90d')}
                className="cursor-pointer text-right"
                style={{ width: '105px' }}
                title="SPI Dasarian 90D: Akumulasi 90 hari (9 dasarian) — Indikator informatif tambahan"
              >
                <div className="th-flex justify-end">
                  <span>SPI 90D</span>
                  {renderSortIcon('spi_value_90d')}
                </div>
              </th>

              {/* 7. Pb20 */}
              <th
                onClick={() => handleSort('prob_below20')}
                className="cursor-pointer text-right th-highlight-prob"
                style={{ width: '90px' }}
                title="Pb20: Probabilitas curah hujan kurang dari 20 mm/dasarian"
              >
                <div className="th-flex justify-end">
                  <span>Pb20</span>
                  {renderSortIcon('prob_below20')}
                </div>
              </th>

              {/* 8. Pa150 */}
              <th
                onClick={() => handleSort('prob_above150')}
                className="cursor-pointer text-right"
                style={{ width: '85px' }}
                title="Pa150: Probabilitas curah hujan dasarian melebihi 150 mm"
              >
                <div className="th-flex justify-end">
                  <span>Pa150</span>
                  {renderSortIcon('prob_above150')}
                </div>
              </th>

              {/* 9. Pa200 */}
              <th
                onClick={() => handleSort('prob_above200')}
                className="cursor-pointer text-right"
                style={{ width: '85px' }}
                title="Pa200: Probabilitas curah hujan dasarian melebihi 200 mm"
              >
                <div className="th-flex justify-end">
                  <span>Pa200</span>
                  {renderSortIcon('prob_above200')}
                </div>
              </th>

              {/* 10. Pa300 */}
              <th
                onClick={() => handleSort('prob_above300')}
                className="cursor-pointer text-right"
                style={{ width: '85px' }}
                title="Pa300: Probabilitas curah hujan dasarian melebihi 300 mm"
              >
                <div className="th-flex justify-end">
                  <span>Pa300</span>
                  {renderSortIcon('prob_above300')}
                </div>
              </th>

              {/* 11. Prob Bulanan >300 mm */}
              <th
                className="text-right"
                style={{ width: '85px' }}
                title="Probabilitas curah hujan bulanan melebihi 300 mm"
              >
                <span>&gt;300mm</span>
              </th>

              {/* 12. Prob Bulanan >400 mm */}
              <th
                className="text-right"
                style={{ width: '85px' }}
                title="Probabilitas curah hujan bulanan melebihi 400 mm"
              >
                <span>&gt;400mm</span>
              </th>

              {/* 13. Prob Bulanan >500 mm */}
              <th
                className="text-right"
                style={{ width: '85px' }}
                title="Probabilitas curah hujan bulanan melebihi 500 mm"
              >
                <span>&gt;500mm</span>
              </th>

              {/* 14. Alasan / Indikator Pemicu */}
              <th
                style={{ minWidth: '200px' }}
                title="Alasan atau indikator ilmiah yang memicu penetapan status peringatan"
              >
                <span>ALASAN PEMICU PERINGATAN</span>
              </th>

              {/* 15. Kelengkapan Evaluasi & Aksi */}
              <th
                className="text-center"
                style={{ width: '130px' }}
                title="Status kelengkapan data & tombol riwayat observasi"
              >
                <span>KELENGKAPAN</span>
              </th>
            </tr>
          </thead>

          <tbody>
            {sortedStations.length === 0 ? (
              <tr>
                <td colSpan={16} className="text-center py-12 text-muted">
                  <div className="empty-search-state">
                    <AlertTriangle size={24} className="text-muted mb-2" />
                    <p className="font-bold">Tidak ada stasiun yang memenuhi kriteria filter.</p>
                    <p className="text-xs">Coba sesuaikan kata kunci pencarian atau pilih filter status 'Semua'.</p>
                  </div>
                </td>
              </tr>
            ) : (
              sortedStations.map((stn) => {
                const isSelected = selectedStationId === stn.station_id;
                const isExpanded = expandedStationId === stn.station_id;
                const isNumericHth = typeof stn.hth_days_current === 'number';
                const hthVal = isNumericHth ? stn.hth_days_current : null;
                const isArg = stn.is_arg || ['21010603B', '21010802B', '21020402B', '21040101B', '21710501B'].includes(stn.station_id);
                const isIncomplete = stn.evaluation_status === 'INCOMPLETE' || stn.data_quality_status === 'INCOMPLETE' || stn.warning_level === 'INCOMPLETE';

                const barWidth = isNumericHth ? Math.min(100, Math.max(0, (Math.min(hthVal, 60) / 60) * 100)) : 0;
                const lvl = (stn.warning_level || 'NORMAL').toLowerCase();
                const cat = (stn.hth_category || 'NORMAL').toLowerCase();
                const hazardLabel = translateHazard(stn.hazard_type);

                const historyObj = rainfallHistoryCache[stn.station_id];
                const isHistoryLoading = rainfallLoadingMap[stn.station_id];

                return (
                  <React.Fragment key={stn.station_id}>
                    <tr
                      className={`early-warning-row ${isSelected ? 'row-selected' : ''} ${isExpanded ? 'row-expanded' : ''}`}
                      onClick={() => onSelectStation && onSelectStation(stn)}
                    >
                      {/* 1. Nama & ID Stasiun (Sticky Column) */}
                      <td className="td-sticky-col">
                        <div className="stn-cell">
                          <span className="stn-name">{stn.station_name}</span>
                          <span className="stn-id font-mono">{stn.station_id}</span>
                        </div>
                      </td>

                      {/* 2. Kabupaten / Kota */}
                      <td>
                        <span className="kab-text">{stn.kabupaten}</span>
                      </td>

                      {/* 3. Jenis Stasiun */}
                      <td className="text-center">
                        <span className="badge-station-tag font-mono text-[10px] text-slate-600 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded">
                          Stasiun
                        </span>
                      </td>

                      {/* 4. Status PDKM (Kekeringan Meteorologis) */}
                      <td className="text-center bg-amber-50/30">
                        {(() => {
                          const pSt = (stn.pdkm_status || 'NORMAL').toUpperCase();
                          const pLvl = pSt.toLowerCase();
                          if (pSt === 'INCOMPLETE' || pSt === 'INSUFFICIENT_DATA') {
                            return (
                              <span className="badge-pill lvl-incomplete" title={stn.pdkm_reasons || 'Data masukan PDKM belum lengkap'}>
                                DATA KURANG
                              </span>
                            );
                          }
                          const isWarning = ['WASPADA', 'SIAGA', 'AWAS'].includes(pSt);
                          return (
                            <span className={`badge-pill lvl-${pLvl}`} title={stn.pdkm_reasons || `PDKM ${pSt}`}>
                              {pSt === 'NORMAL' ? 'AMAN' : pSt}
                            </span>
                          );
                        })()}
                      </td>

                      {/* 5. Status PDCHT (Curah Hujan Tinggi) */}
                      <td className="text-center bg-blue-50/30">
                        {(() => {
                          const rSt = (stn.pdcht_status || 'NORMAL').toUpperCase();
                          const rLvl = rSt.toLowerCase();
                          if (rSt === 'INCOMPLETE' || rSt === 'INSUFFICIENT_DATA') {
                            return (
                              <span className="badge-pill lvl-incomplete" title={stn.pdcht_reasons || 'Data masukan PDCHT belum lengkap'}>
                                DATA KURANG
                              </span>
                            );
                          }
                          return (
                            <span className={`badge-pill lvl-${rLvl}`} title={stn.pdcht_reasons || `PDCHT ${rSt}`}>
                              {rSt === 'NORMAL' ? 'AMAN' : rSt}
                            </span>
                          );
                        })()}
                      </td>

                      {/* 5. HTH Aktual */}
                      <td>
                        {isNumericHth ? (
                          <div className="hth-bar-cell">
                            <span className="hth-num font-mono">
                              {hthVal} hr
                              {stn.hth_uncertain && (
                                <span className="hth-uncertain-mark" title="Penghitungan HTH terhalang data missing">(?)</span>
                              )}
                            </span>
                            <div className="hth-progress-track" title={`HTH: ${hthVal} hari (${stn.hth_category || 'Normal'})`}>
                              <div
                                className={`hth-progress-bar bar-${cat}`}
                                style={{ width: `${barWidth}%` }}
                              />
                            </div>
                          </div>
                        ) : (
                          <div className="hth-bar-cell justify-end">
                            <span className="text-muted font-mono">—</span>
                          </div>
                        )}
                      </td>

                      {/* 6. SPI Dasarian 30D */}
                      <td className="text-right">
                        {isArg ? (
                          <span className="text-muted font-mono" title="Data SPI tidak tersedia">—</span>
                        ) : typeof stn.spi_value === 'number' ? (
                          <div className="spi-cell-container text-right">
                            <span className={`font-mono spi-val ${stn.spi_value <= -1.5 ? 'spi-drought' : stn.spi_value >= 1.5 ? 'spi-wet' : ''}`}>
                              {stn.spi_value.toFixed(2)}
                            </span>
                            {stn.spi_validation_status === 'NOT_VERIFIED' && (
                              <span className="spi-unverified-tag" title="Data SPI 30D belum terverifikasi (NOT VERIFIED)">*</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted font-mono">—</span>
                        )}
                      </td>

                      {/* 7. SPI Dasarian 90D */}
                      <td className="text-right">
                        {isArg ? (
                          <span className="text-muted font-mono" title="Data SPI tidak tersedia">—</span>
                        ) : typeof stn.spi_value_90d === 'number' ? (
                          <div className="spi-cell-container text-right">
                            <span className={`font-mono spi-val ${stn.spi_value_90d <= -1.5 ? 'spi-drought' : stn.spi_value_90d >= 1.5 ? 'spi-wet' : ''}`}>
                              {stn.spi_value_90d.toFixed(2)}
                            </span>
                            {stn.spi_validation_status_90d === 'NOT_VERIFIED' && (
                              <span className="spi-unverified-tag" title="Data SPI 90D belum terverifikasi (NOT VERIFIED)">*</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted font-mono">—</span>
                        )}
                      </td>

                      {/* 7. Pb20 (< 20 mm) */}
                      <td className="text-right th-highlight-prob font-mono">
                        {isArg ? (
                          <span className="text-muted">—</span>
                        ) : typeof stn.prob_below20 === 'number' ? (
                          <span className={stn.prob_below20 > 70 ? 'prob-high-danger' : stn.prob_below20 >= 50 ? 'prob-medium-alert' : ''}>
                            {formatProb(stn.prob_below20, isArg)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* 8. Pa150 (> 150 mm) */}
                      <td className="text-right font-mono">
                        {isArg ? (
                          <span className="text-muted">—</span>
                        ) : typeof stn.prob_above150 === 'number' ? (
                          <span className={stn.prob_above150 > 50 ? 'prob-high-danger' : ''}>
                            {formatProb(stn.prob_above150, isArg)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* 9. Pa200 (> 200 mm) */}
                      <td className="text-right font-mono">
                        {isArg ? (
                          <span className="text-muted">—</span>
                        ) : typeof stn.prob_above200 === 'number' ? (
                          <span className={stn.prob_above200 > 50 ? 'prob-high-danger' : ''}>
                            {formatProb(stn.prob_above200, isArg)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* 10. Pa300 (> 300 mm) */}
                      <td className="text-right font-mono">
                        {isArg ? (
                          <span className="text-muted">—</span>
                        ) : typeof stn.prob_above300 === 'number' ? (
                          <span className={stn.prob_above300 > 50 ? 'prob-high-danger' : ''}>
                            {formatProb(stn.prob_above300, isArg)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* 11. Bulanan > 300 mm */}
                      <td className="text-right font-mono">
                        {isArg ? (
                          <span className="text-muted">—</span>
                        ) : typeof stn.prob_month_above300 === 'number' ? (
                          <span className={stn.prob_month_above300 > 50 ? 'prob-high-danger' : ''}>
                            {formatProb(stn.prob_month_above300, isArg)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* 12. Bulanan > 400 mm */}
                      <td className="text-right font-mono">
                        {isArg ? (
                          <span className="text-muted">—</span>
                        ) : typeof stn.prob_month_above400 === 'number' ? (
                          <span className={stn.prob_month_above400 > 50 ? 'prob-high-danger' : ''}>
                            {formatProb(stn.prob_month_above400, isArg)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* 13. Bulanan > 500 mm */}
                      <td className="text-right font-mono">
                        {isArg ? (
                          <span className="text-muted">—</span>
                        ) : typeof stn.prob_month_above500 === 'number' ? (
                          <span className={stn.prob_month_above500 > 50 ? 'prob-high-danger' : ''}>
                            {formatProb(stn.prob_month_above500, isArg)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* 14. Alasan Pemicu Peringatan */}
                      <td>
                        <span className="reason-narrative-text" title={stn.trigger_reason || '—'}>
                          {isArg
                            ? 'Data pendukung belum lengkap'
                            : (stn.trigger_reason || 'Indikator dalam batas normal')}
                        </span>
                      </td>

                      {/* 15. Kelengkapan Evaluasi & Aksi Riwayat */}
                      <td className="text-center">
                        <div className="eval-actions-cell">
                          <span className={`eval-status-badge ${isIncomplete ? 'eval-inc' : 'eval-complete'}`}>
                            {isIncomplete ? 'Parsial' : 'Lengkap'}
                          </span>
                          <button
                            type="button"
                            className={`btn-ch-history-toggle ${isExpanded ? 'active' : ''}`}
                            title={`Lihat riwayat observasi curah hujan ${stn.station_name}`}
                            onClick={(e) => handleToggleRainfall(e, stn)}
                          >
                            <CalendarDays size={11} />
                            <span>CH</span>
                            {isExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* Expandable Riwayat Curah Hujan Harian Row */}
                    {isExpanded && (
                      <tr className="rainfall-history-expanded-row">
                        <td colSpan={16}>
                          <div className="rainfall-history-panel">
                            <RainfallObservationSummary
                              data={historyObj?.data || []}
                              periodStart={historyObj?.period_start}
                              periodEnd={historyObj?.period_end}
                              stationName={stn.station_name}
                              stationId={stn.station_id}
                              loading={isHistoryLoading}
                              error={historyObj?.error}
                              showTableToggle={true}
                            />
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Re-export alias for clean naming
export { HthTable as EarlyWarningTable };
