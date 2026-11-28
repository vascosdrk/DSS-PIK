import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search,
  RotateCcw,
  AlertCircle,
  Percent,
  UploadCloud,
  ShieldAlert,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import './ProbabilityDataTable.css';

export default function ProbabilityDataTable({
  onOpenDownload,
  activePeriodId = '2026-10-das3',
  onOpenIngestion,
  onOpenManagement,
  externalResolutionMode = null,
  onResolutionChange = null,
  embeddedMode = false,
}) {
  // Resolution Switch: DASARIAN vs BULANAN
  const [resolutionMode, setResolutionMode] = useState(
    externalResolutionMode || (activePeriodId && !activePeriodId.includes('das') ? 'BULANAN' : 'DASARIAN')
  );

  const [selectedPeriodId, setSelectedPeriodId] = useState(activePeriodId);
  const [selectedIssueDate, setSelectedIssueDate] = useState('');
  const [periodsList, setPeriodsList] = useState([]);
  const [probPeriodsData, setProbPeriodsData] = useState({ dasarian: [], bulanan: [] });
  const [probRows, setProbRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters State
  const [searchQuery, setSearchQuery] = useState('');
  const [kabupatenFilter, setKabupatenFilter] = useState('ALL');

  // Load available periods dynamically from API (from cews_forecast_snapshot)
  const fetchAvailablePeriods = useCallback(() => {
    authFetch(API_ENDPOINTS.PROBABILITY_PERIODS)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (data && (data.dasarian || data.bulanan)) {
          setProbPeriodsData(data);
          const currentList = resolutionMode === 'BULANAN' ? (data.bulanan || []) : (data.dasarian || []);
          setPeriodsList(currentList);

          // If selectedPeriodId not in list, auto-select first available
          if (currentList.length > 0) {
            const hasMatch = currentList.some((p) => p.period_id === selectedPeriodId);
            if (!hasMatch) {
              setSelectedPeriodId(currentList[0].period_id);
            }
          }
        }
      })
      .catch((err) => {
        console.warn('Fallback to standard PERIODS endpoint:', err);
        authFetch(API_ENDPOINTS.PERIODS)
          .then((res) => res.json())
          .then((data) => {
            if (data && Array.isArray(data.periods)) {
              setPeriodsList(data.periods);
            }
          })
          .catch((e) => console.error('Failed to load fallback periods:', e));
      });
  }, [resolutionMode, selectedPeriodId]);

  useEffect(() => {
    fetchAvailablePeriods();
  }, [resolutionMode]);

  // Handle Switch Resolution
  const handleSwitchResolution = (newRes) => {
    if (newRes !== resolutionMode) {
      setResolutionMode(newRes);
      if (onResolutionChange) {
        onResolutionChange(newRes);
      }
      const targetList = newRes === 'BULANAN' ? probPeriodsData.bulanan : probPeriodsData.dasarian;
      if (targetList && targetList.length > 0) {
        setSelectedPeriodId(targetList[0].period_id);
      } else {
        setSelectedPeriodId(newRes === 'BULANAN' ? '2026-10' : '2026-10-das3');
      }
      setSelectedIssueDate('');
    }
  };

  // Sync with externalResolutionMode from 2-level Resolusi Prakiraan filter
  useEffect(() => {
    if (externalResolutionMode && externalResolutionMode !== resolutionMode) {
      setResolutionMode(externalResolutionMode);
      const targetList =
        externalResolutionMode === 'BULANAN' ? probPeriodsData.bulanan : probPeriodsData.dasarian;
      if (targetList && targetList.length > 0) {
        setSelectedPeriodId(targetList[0].period_id);
      } else {
        setSelectedPeriodId(externalResolutionMode === 'BULANAN' ? '2026-10' : '2026-10-das3');
      }
      setSelectedIssueDate('');
      setKabupatenFilter('ALL');
      setSearchQuery('');
    }
  }, [externalResolutionMode]);

  // Sync with activePeriodId prop if changed from parent
  useEffect(() => {
    if (activePeriodId) {
      setSelectedPeriodId(activePeriodId);
      if (activePeriodId.includes('das')) {
        setResolutionMode('DASARIAN');
      } else {
        setResolutionMode('BULANAN');
      }
      setSelectedIssueDate('');
    }
  }, [activePeriodId]);

  // Fetch Probability Data
  const fetchProbabilityData = useCallback(() => {
    setLoading(true);
    setError(null);

    const params = {
      period_id: selectedPeriodId,
      page_size: 100, // 57 stations in Kepri
    };
    if (selectedIssueDate) {
      params.issue_date = selectedIssueDate;
    }

    const url = API_ENDPOINTS.PROBABILITY_DATA(params);

    authFetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat data probabilitas`);
        return res.json();
      })
      .then((data) => {
        setProbRows(data.data || []);
        setMeta(data.meta || null);
        if (!selectedIssueDate && data.meta?.active_vintage_issue) {
          setSelectedIssueDate(data.meta.active_vintage_issue);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch probability data:', err);
        setError('Gagal memuat dataset probabilitas prakiraan dari server.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedPeriodId, selectedIssueDate]);

  useEffect(() => {
    if (selectedPeriodId) {
      fetchProbabilityData();
    }
  }, [fetchProbabilityData, selectedPeriodId]);

  // Unique Kabupatens for dropdown
  const kabupatenList = useMemo(() => {
    const set = new Set();
    probRows.forEach((r) => {
      if (r.kabupaten) set.add(r.kabupaten);
    });
    return Array.from(set).sort();
  }, [probRows]);

  // Filtered rows based on search and kabupaten, sorted strictly by kabupaten then station_name
  const filteredRows = useMemo(() => {
    const list = probRows.filter((r) => {
      if (kabupatenFilter !== 'ALL' && r.kabupaten !== kabupatenFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchName = (r.station_name || '').toLowerCase().includes(q);
        const matchId = (r.station_id || '').toLowerCase().includes(q);
        const matchKab = (r.kabupaten || '').toLowerCase().includes(q);
        if (!matchName && !matchId && !matchKab) return false;
      }
      return true;
    });

    // Enforce canonical 57 station ordering matching DailyRainfallTable & SpiDataTable
    return [...list].sort((a, b) => {
      const kabA = (a.kabupaten || '').localeCompare(b.kabupaten || '');
      if (kabA !== 0) return kabA;
      return (a.station_name || '').localeCompare(b.station_name || '');
    });
  }, [probRows, kabupatenFilter, searchQuery]);

  const resolution = meta?.resolution || resolutionMode;
  const availableVintages = meta?.available_vintages || [];
  const activeIssue = meta?.active_vintage_issue || selectedIssueDate;
  const isLatestVintage = availableVintages.length > 0 && activeIssue === availableVintages[0];

  // Format probability strictly in 0-100% scale (PDKM pb20 > 70%, PDCHT pa/pm > 50%)
  const formatProb = (val, threshold = 50.0, alertKind = 'pdcht') => {
    if (val === null || val === undefined) {
      return <span className="prob-v2-val-empty">—</span>;
    }
    const num = Number(val);
    const isAlert = num > threshold;
    const alertClass = isAlert
      ? (alertKind === 'pdkm' ? 'prob-v2-val-alert-pdkm' : 'prob-v2-val-alert-pdcht')
      : '';
    return (
      <span className={`prob-v2-val ${alertClass}`}>
        {num.toFixed(1)}%
      </span>
    );
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setKabupatenFilter('ALL');
    if (availableVintages.length > 0) {
      setSelectedIssueDate(availableVintages[0]);
    }
  };

  return (
    <div className="prob-v2-page">
      {/* 1. Compact Operational Page Header (shown only when standalone) */}
      {!embeddedMode && (
      <div className="prob-v2-header">
        <div className="prob-v2-title-group">
          <div className="prob-v2-icon-box">
            <Percent size={20} />
          </div>
          <div>
            <div className="prob-v2-title-row">
              <h2 className="prob-v2-title">Tabel Prakiraan Probabilistik ECMWF</h2>
              <span className="prob-v2-res-pill">{resolution}</span>
            </div>
            <p className="prob-v2-desc">
              Prakiraan probabilistik ensemble ECMWF 57 pos Kepulauan Riau · Ambang pemicu <strong>PDKM (pb20) &gt; 70.0%</strong> &amp; <strong>PDCHT &gt; 50.0%</strong>
            </p>
          </div>
        </div>

        <div className="prob-v2-header-right">
          <div className="prob-v2-meta-cards">
            <div className="prob-v2-meta-card">
              <span className="prob-v2-meta-label">Cakupan</span>
              <span className="prob-v2-meta-value">{probRows.length || 57} Pos</span>
            </div>
            <div className="prob-v2-meta-card">
              <span className="prob-v2-meta-label">Penerbitan (Vintage)</span>
              <span className="prob-v2-meta-value font-mono">
                <span className={`prob-v2-status-dot ${isLatestVintage ? '' : 'historic'}`} />
                {activeIssue || 'Tidak tersedia'}
              </span>
            </div>
          </div>

          <div className="prob-v2-actions">
            {onOpenIngestion && (
              <button
                type="button"
                className="prob-v2-btn-primary"
                onClick={() => onOpenIngestion(resolutionMode === 'BULANAN' ? 'PROBABILITAS_BULANAN' : 'PROBABILITAS_DASARIAN')}
                title="Buka modul upload file Excel Probabilitas ECMWF"
              >
                <UploadCloud size={15} />
                <span>Input / Pembaruan Data</span>
              </button>
            )}
            {onOpenManagement && (
              <button
                type="button"
                className="prob-v2-btn-secondary"
                onClick={() => onOpenManagement('CORRECTIONS', 'PROBABILITAS')}
                title="Buka panel Kelola Vintage Probabilitas ECMWF"
              >
                <ShieldAlert size={14} className="text-rose-600" />
                <span>Kelola Vintage</span>
              </button>
            )}
          </div>
        </div>
      </div>
      )}

      {/* 2. Unified Filter Bar (Resolution switch omitted when embeddedMode=true) */}
      <div className="prob-v2-controls-card">
        <div className="prob-v2-controls-top">
          {!embeddedMode ? (
          <div className="prob-v2-seg-wrap">
            <span className="prob-v2-seg-label">Resolusi Prakiraan</span>
            <div className="prob-v2-segmented" role="group" aria-label="Resolusi Probabilitas">
              <button
                type="button"
                className={`prob-v2-seg-btn ${resolutionMode === 'DASARIAN' ? 'active' : ''}`}
                onClick={() => handleSwitchResolution('DASARIAN')}
                aria-pressed={resolutionMode === 'DASARIAN'}
              >
                <span>Dasarian</span>
                <span className="prob-v2-seg-sub">(pb20, pa150, pa200, pa300)</span>
              </button>
              <button
                type="button"
                className={`prob-v2-seg-btn ${resolutionMode === 'BULANAN' ? 'active' : ''}`}
                onClick={() => handleSwitchResolution('BULANAN')}
                aria-pressed={resolutionMode === 'BULANAN'}
              >
                <span>Bulanan</span>
                <span className="prob-v2-seg-sub">(pa300, pa400, pa500)</span>
              </button>
            </div>
          </div>
          ) : (
          <div className="ecmwf-inline-title-row">
            <h3 className="ecmwf-inline-title">Tabel Prakiraan Probabilistik ECMWF</h3>
            <span className="ecmwf-inline-meta">Cakupan: {probRows.length || 57} Pos</span>
            <span className="ecmwf-inline-meta font-mono">
              <span className={`prob-v2-status-dot ${isLatestVintage ? '' : 'historic'}`} />
              Vintage: {activeIssue || 'Tidak tersedia'}
            </span>
          </div>
          )}

          <div className="prob-v2-count-summary">
            Menampilkan <strong>{filteredRows.length}</strong> dari <strong>{probRows.length}</strong> pos
          </div>
        </div>

        <div className="prob-v2-filter-row">
          <div className="prob-v2-field prob-v2-field-period">
            <label className="prob-v2-label" htmlFor="prob-period-select">Periode Target</label>
            <select
              id="prob-period-select"
              className="prob-v2-select font-mono"
              value={selectedPeriodId}
              onChange={(e) => {
                setSelectedPeriodId(e.target.value);
                setSelectedIssueDate('');
              }}
            >
              {periodsList.length === 0 ? (
                <option value={selectedPeriodId}>{selectedPeriodId}</option>
              ) : (
                periodsList.map((p) => (
                  <option key={p.period_id} value={p.period_id}>
                    {p.label || p.period_id} {p.date_range ? `(${p.date_range})` : ''}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="prob-v2-field">
            <label className="prob-v2-label" htmlFor="prob-vintage-select">Penerbitan (Vintage)</label>
            <select
              id="prob-vintage-select"
              className="prob-v2-select font-mono"
              value={selectedIssueDate}
              onChange={(e) => setSelectedIssueDate(e.target.value)}
              disabled={availableVintages.length <= 1}
            >
              {availableVintages.length === 0 ? (
                <option value="">Belum Ada Vintage</option>
              ) : (
                availableVintages.map((vDate, idx) => (
                  <option key={vDate} value={vDate}>
                    {vDate} {idx === 0 ? '(Aktif)' : '(Historis)'}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="prob-v2-field">
            <label className="prob-v2-label" htmlFor="prob-kab-select">Wilayah</label>
            <select
              id="prob-kab-select"
              className="prob-v2-select"
              value={kabupatenFilter}
              onChange={(e) => setKabupatenFilter(e.target.value)}
            >
              <option value="ALL">Semua Kabupaten/Kota</option>
              {kabupatenList.map((kab) => (
                <option key={kab} value={kab}>{kab}</option>
              ))}
            </select>
          </div>

          <div className="prob-v2-field prob-v2-field-search">
            <label className="prob-v2-label" htmlFor="prob-station-search">Cari Stasiun</label>
            <div className="prob-v2-search-box">
              <Search size={14} className="prob-v2-search-icon" />
              <input
                id="prob-station-search"
                type="text"
                className="prob-v2-input"
                placeholder="Cari nama stasiun, ID pos, atau wilayah..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  className="prob-v2-search-clear"
                  onClick={() => setSearchQuery('')}
                  aria-label="Hapus pencarian"
                >
                  &times;
                </button>
              )}
            </div>
          </div>

          <button
            type="button"
            className="prob-v2-btn-reset"
            onClick={handleResetFilters}
            title="Reset filter wilayah, pencarian, dan kembalikan ke vintage aktif"
          >
            <RotateCcw size={13} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* 3. Probability Table Card (Single Scroll Container + Proper Sticky Header) */}
      <div className="prob-v2-table-card">
        {loading && (
          <div className="prob-v2-loading">
            <div className="prob-v2-spinner" />
            <span>Memuat parameter probabilitas ECMWF...</span>
          </div>
        )}

        {error && (
          <div className="prob-v2-error">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && (
          <div className="prob-v2-scroll">
            <table className="prob-v2-table">
              <thead>
                <tr>
                  <th className="prob-v2-col-no col-center">No</th>
                  <th className="prob-v2-col-id">ID Pos</th>
                  <th className="prob-v2-col-name">Nama Pos Hujan</th>
                  <th style={{ minWidth: '150px' }}>Wilayah</th>
                  <th style={{ minWidth: '112px' }} className="col-center">Issue Date</th>
                  {resolution === 'DASARIAN' ? (
                    <>
                      <th className="col-num col-pdkm" style={{ minWidth: '116px' }} title="Peluang CH Dasarian < 20 mm (PDKM)">
                        pb20
                        <span className="prob-v2-th-sub">&lt; 20 mm</span>
                      </th>
                      <th className="col-num col-pdcht" style={{ minWidth: '116px' }} title="Peluang CH Dasarian > 150 mm (PDCHT Waspada)">
                        pa150
                        <span className="prob-v2-th-sub">&gt; 150 mm</span>
                      </th>
                      <th className="col-num col-pdcht" style={{ minWidth: '116px' }} title="Peluang CH Dasarian > 200 mm (PDCHT Siaga)">
                        pa200
                        <span className="prob-v2-th-sub">&gt; 200 mm</span>
                      </th>
                      <th className="col-num col-pdcht" style={{ minWidth: '116px' }} title="Peluang CH Dasarian > 300 mm (PDCHT Awas)">
                        pa300
                        <span className="prob-v2-th-sub">&gt; 300 mm</span>
                      </th>
                    </>
                  ) : (
                    <>
                      <th className="col-num col-pdcht" style={{ minWidth: '130px' }} title="Peluang CH Bulanan > 300 mm (PDCHT Waspada)">
                        pa300
                        <span className="prob-v2-th-sub">&gt; 300 mm/bln</span>
                      </th>
                      <th className="col-num col-pdcht" style={{ minWidth: '130px' }} title="Peluang CH Bulanan > 400 mm (PDCHT Siaga)">
                        pa400
                        <span className="prob-v2-th-sub">&gt; 400 mm/bln</span>
                      </th>
                      <th className="col-num col-pdcht" style={{ minWidth: '130px' }} title="Peluang CH Bulanan > 500 mm (PDCHT Awas)">
                        pa500
                        <span className="prob-v2-th-sub">&gt; 500 mm/bln</span>
                      </th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan={resolution === 'DASARIAN' ? 9 : 8} className="py-12 text-center text-slate-400 italic">
                      Tidak ada rekaman data probabilitas untuk periode {selectedPeriodId}.
                    </td>
                  </tr>
                ) : (
                  filteredRows.map((r, idx) => (
                    <tr key={r.station_id}>
                      <td className="prob-v2-col-no col-center font-mono text-slate-400 text-xs">
                        {idx + 1}
                      </td>
                      <td className="prob-v2-col-id font-mono text-slate-900 font-semibold">
                        {r.station_id}
                      </td>
                      <td className="prob-v2-col-name text-slate-800 font-medium">
                        {r.station_name}
                      </td>
                      <td className="text-slate-600">
                        {r.kabupaten || '—'}
                      </td>
                      <td className="col-center font-mono text-slate-500 text-xs">
                        {r.forecast_issue && r.forecast_issue !== 'TIDAK_TERSEDIA' ? r.forecast_issue : '—'}
                      </td>
                      {resolution === 'DASARIAN' ? (
                        <>
                          <td className="col-num">
                            {r.is_arg ? <span className="prob-v2-val-empty" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_below20, 70.0, 'pdkm')}
                          </td>
                          <td className="col-num">
                            {r.is_arg ? <span className="prob-v2-val-empty" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_above150, 50.0, 'pdcht')}
                          </td>
                          <td className="col-num">
                            {r.is_arg ? <span className="prob-v2-val-empty" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_above200, 50.0, 'pdcht')}
                          </td>
                          <td className="col-num">
                            {r.is_arg ? <span className="prob-v2-val-empty" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_above300, 50.0, 'pdcht')}
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="col-num">
                            {r.is_arg ? <span className="prob-v2-val-empty" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_month_above300, 50.0, 'pdcht')}
                          </td>
                          <td className="col-num">
                            {r.is_arg ? <span className="prob-v2-val-empty" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_month_above400, 50.0, 'pdcht')}
                          </td>
                          <td className="col-num">
                            {r.is_arg ? <span className="prob-v2-val-empty" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_month_above500, 50.0, 'pdcht')}
                          </td>
                        </>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 4. Clean Table Footer */}
        <div className="prob-v2-footer">
          <div className="prob-v2-footer-meta">
            <span>
              Menampilkan <strong>{filteredRows.length}</strong> dari <strong>{probRows.length}</strong> Stasiun Master
              {searchQuery ? ` (disaring: "${searchQuery}")` : ''}
            </span>
            <span className={`prob-v2-vintage-tag ${isLatestVintage ? '' : 'historic'}`}>
              <span className={`prob-v2-status-dot ${isLatestVintage ? '' : 'historic'}`} />
              {isLatestVintage ? 'Vintage Aktif Terbaru' : 'Vintage Historis'}
            </span>
          </div>
          <div className="prob-v2-legend">
            <span className="prob-v2-legend-item">
              <span className="prob-v2-swatch pdkm" />
              PDKM (pb20 &gt; 70.0%)
            </span>
            <span className="prob-v2-legend-item">
              <span className="prob-v2-swatch pdcht" />
              PDCHT (pa &gt; 50.0%)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
