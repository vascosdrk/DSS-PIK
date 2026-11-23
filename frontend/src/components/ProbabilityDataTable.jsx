import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Calendar, 
  Search, 
  Download, 
  RotateCcw, 
  Activity, 
  AlertCircle, 
  Radio, 
  Percent,
  SlidersHorizontal,
  ChevronDown,
  UploadCloud,
  TrendingUp,
  History,
  Layers,
  ShieldAlert,
  FileSpreadsheet,
  CheckCircle2
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import { formatDateIndo } from '../utils/formatters';

export default function ProbabilityDataTable({
  onOpenDownload,
  activePeriodId = '2026-10-das3',
  onOpenIngestion,
  onOpenManagement,
}) {
  // Resolution Switch: DASARIAN vs BULANAN
  const [resolutionMode, setResolutionMode] = useState(
    activePeriodId && !activePeriodId.includes('das') ? 'BULANAN' : 'DASARIAN'
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
    // 1. Fetch dynamic forecast periods
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
        // Fallback to legacy periods endpoint
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
      const targetList = newRes === 'BULANAN' ? probPeriodsData.bulanan : probPeriodsData.dasarian;
      if (targetList && targetList.length > 0) {
        setSelectedPeriodId(targetList[0].period_id);
      } else {
        setSelectedPeriodId(newRes === 'BULANAN' ? '2026-10' : '2026-10-das3');
      }
      setSelectedIssueDate('');
    }
  };

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

  // Helper to format probability strictly in 0–100% scale (PDKM pb20 > 70%, PDCHT pa/pm > 50%)
  const formatProb = (val, threshold = 50.0) => {
    if (val === null || val === undefined) {
      return <span className="text-slate-400 font-mono text-xs select-none">—</span>;
    }
    const num = Number(val);
    const isAlert = num > threshold;
    return (
      <span className={`prob-value-cell font-mono ${isAlert ? 'prob-high-alert font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded border border-amber-300 shadow-xs' : 'text-slate-700'}`}>
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
    <div className="rainfall-table-page">
      {/* 1. Page Header matching DailyRainfallTable */}
      <div className="rainfall-page-header">
        <div className="rainfall-page-title-group">
          <div className="rainfall-title-icon-box bg-purple-50 text-purple-700 border border-purple-200">
            <Percent size={24} className="text-purple-700" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="rainfall-page-title">Tabel Prakiraan Probabilistik ECMWF</h2>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${
                resolution === 'DASARIAN' ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-indigo-50 text-indigo-700 border-indigo-200'
              }`}>
                {resolution}
              </span>
            </div>
            <p className="rainfall-page-desc text-xs text-slate-500 mt-0.5">
              Snapshot ensemble probabilistik ECMWF untuk 57 stasiun Kepri. Ambang pemicu: <strong>PDKM (pb20) &gt; 70.0%</strong> &bull; <strong>PDCHT &gt; 50.0%</strong>.
            </p>
          </div>
        </div>

        <div className="rainfall-header-meta">
          <div className="badge-meta-box">
            <span className="badge-meta-label">Cakupan Stasiun</span>
            <span className="badge-meta-value">57 Stasiun</span>
          </div>
          <div className="badge-meta-box">
            <span className="badge-meta-label">Penerbitan (Vintage)</span>
            <span className="badge-meta-value font-mono">{activeIssue ? activeIssue : 'TIDAK TERSEDIA'}</span>
          </div>

          <div className="flex items-center flex-wrap gap-2">
            {onOpenIngestion && (
              <button
                type="button"
                className="btn-input-rainfall-cta bg-purple-700 hover:bg-purple-800"
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
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-300 transition"
                onClick={() => onOpenManagement('CORRECTIONS', 'PROBABILITAS')}
                title="Buka formulir pembatalan (void) snapshot probabilitas ECMWF"
              >
                <ShieldAlert size={13} className="text-rose-600" />
                <span>Pembatalan / Void</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 2. Switch Controls Bar: Resolution Mode */}
      <div className="spi-controls-card mb-3">
        <div className="spi-switch-group">
          <div className="switch-item">
            <span className="switch-label">Resolusi Prakiraan:</span>
            <div className="segmented-switch" role="group" aria-label="Resolusi Probabilitas">
              <button
                type="button"
                className={`switch-btn ${resolutionMode === 'DASARIAN' ? 'active' : ''}`}
                onClick={() => handleSwitchResolution('DASARIAN')}
              >
                PROBABILITAS DASARIAN (pb20, pa150, pa200, pa300)
              </button>
              <button
                type="button"
                className={`switch-btn ${resolutionMode === 'BULANAN' ? 'active' : ''}`}
                onClick={() => handleSwitchResolution('BULANAN')}
              >
                PROBABILITAS BULANAN (pa300, pa400, pa500)
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Filter Toolbar matching DailyRainfallTable */}
      <div className="rainfall-toolbar">
        <div className="toolbar-filters-row">
          {/* Periode Target Dropdown */}
          <div className="filter-item-group">
            <label className="filter-label">Periode Target</label>
            <select
              className="toolbar-select font-mono text-xs"
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

          {/* Model Vintage Issue Date */}
          <div className="filter-item-group">
            <label className="filter-label">Penerbitan (Vintage)</label>
            <select
              className="toolbar-select font-mono text-xs"
              value={selectedIssueDate}
              onChange={(e) => setSelectedIssueDate(e.target.value)}
              disabled={availableVintages.length <= 1}
            >
              {availableVintages.length === 0 ? (
                <option value="">Belum Ada Vintage</option>
              ) : (
                availableVintages.map((vDate, idx) => (
                  <option key={vDate} value={vDate}>
                    {vDate} {idx === 0 ? '(Aktif / Terbaru)' : '(Historis)'}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Kabupaten Filter */}
          <div className="filter-item-group">
            <label className="filter-label">Wilayah</label>
            <select
              className="toolbar-select"
              value={kabupatenFilter}
              onChange={(e) => setKabupatenFilter(e.target.value)}
            >
              <option value="ALL">Semua Kabupaten/Kota</option>
              {kabupatenList.map((kab) => (
                <option key={kab} value={kab}>{kab}</option>
              ))}
            </select>
          </div>

          {/* Search Box */}
          <div className="filter-item-group flex-1 min-w-[200px]">
            <label className="filter-label">Cari Stasiun</label>
            <div className="toolbar-search-wrapper">
              <Search size={14} className="toolbar-search-icon" />
              <input
                type="text"
                className="toolbar-search-input"
                placeholder="Cari nama stasiun atau ID pos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  className="toolbar-search-clear"
                  onClick={() => setSearchQuery('')}
                >
                  &times;
                </button>
              )}
            </div>
          </div>

          {/* Reset Action */}
          <div className="filter-actions-group">
            <button
              type="button"
              className="btn-reset-filters"
              onClick={handleResetFilters}
              title="Reset seluruh filter pencarian dan kembalikan vintage"
            >
              <RotateCcw size={13} />
              <span>Reset</span>
            </button>
          </div>
        </div>
      </div>

      {/* 4. Table Card Container */}
      <div className="prob-table-wrapper">
        {loading && (
          <div className="table-loading-overlay py-12 flex flex-col items-center justify-center space-y-2 text-slate-500 text-xs">
            <div className="w-7 h-7 border-3 border-purple-600 border-t-transparent rounded-full animate-spin" />
            <span>Memuat parameter probabilitas ECMWF dari database kanonikal...</span>
          </div>
        )}

        {error && (
          <div className="p-4 bg-rose-50 border-b border-rose-200 text-rose-700 text-xs flex items-center space-x-2">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && (
          <div className="rainfall-table-scroll-container max-h-[640px] overflow-auto">
            <table className="prob-structured-table">
              <thead>
                <tr className="th-prob-sub-row">
                  <th className="th-sticky-date text-center w-12" style={{ width: '48px' }}>No</th>
                  <th className="th-sticky-id w-28">ID Pos</th>
                  <th className="th-sticky-name min-w-[200px]">Nama Pos Hujan</th>
                  <th className="w-36">Wilayah</th>
                  <th className="w-28 font-mono">Issue Date</th>
                  {resolution === 'DASARIAN' ? (
                    <>
                      <th className="text-right w-28 text-amber-900 bg-amber-50/70" title="Peluang CH Dasarian < 20 mm (PDKM)">pb20 (&lt;20mm)</th>
                      <th className="text-right w-28 text-blue-900 bg-blue-50/70" title="Peluang CH Dasarian > 150 mm (PDCHT Waspada)">pa150 (&gt;150mm)</th>
                      <th className="text-right w-28 text-blue-900 bg-blue-50/70" title="Peluang CH Dasarian > 200 mm (PDCHT Siaga)">pa200 (&gt;200mm)</th>
                      <th className="text-right w-28 text-indigo-900 bg-indigo-50/70" title="Peluang CH Dasarian > 300 mm (PDCHT Awas)">pa300 (&gt;300mm)</th>
                    </>
                  ) : (
                    <>
                      <th className="text-right w-32 text-blue-900 bg-blue-50/70" title="Peluang CH Bulanan > 300 mm (PDCHT Waspada)">pa300 (&gt;300mm/bln)</th>
                      <th className="text-right w-32 text-blue-900 bg-blue-50/70" title="Peluang CH Bulanan > 400 mm (PDCHT Siaga)">pa400 (&gt;400mm/bln)</th>
                      <th className="text-right w-32 text-indigo-900 bg-indigo-50/70" title="Peluang CH Bulanan > 500 mm (PDCHT Awas)">pa500 (&gt;500mm/bln)</th>
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
                    <tr key={r.station_id} className="hover:bg-slate-50 transition-colors">
                      <td className="td-sticky-date text-center font-mono text-slate-400 text-xs">
                        {idx + 1}
                      </td>
                      <td className="td-sticky-id font-mono text-slate-900 font-semibold">
                        {r.station_id}

                      </td>
                      <td className="td-sticky-name text-slate-800 font-medium">
                        {r.station_name}
                      </td>
                      <td className="text-slate-600">
                        {r.kabupaten || '—'}
                      </td>
                      <td className="font-mono text-slate-500 text-[11px]">
                        {r.forecast_issue && r.forecast_issue !== 'TIDAK_TERSEDIA' ? r.forecast_issue : '—'}
                      </td>
                      {resolution === 'DASARIAN' ? (
                        <>
                          <td className="text-right">
                            {r.is_arg ? <span className="text-slate-400 font-mono text-xs" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_below20, 70.0)}
                          </td>
                          <td className="text-right">
                            {r.is_arg ? <span className="text-slate-400 font-mono text-xs" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_above150, 50.0)}
                          </td>
                          <td className="text-right">
                            {r.is_arg ? <span className="text-slate-400 font-mono text-xs" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_above200, 50.0)}
                          </td>
                          <td className="text-right">
                            {r.is_arg ? <span className="text-slate-400 font-mono text-xs" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_above300, 50.0)}
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="text-right">
                            {r.is_arg ? <span className="text-slate-400 font-mono text-xs" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_month_above300, 50.0)}
                          </td>
                          <td className="text-right">
                            {r.is_arg ? <span className="text-slate-400 font-mono text-xs" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_month_above400, 50.0)}
                          </td>
                          <td className="text-right">
                            {r.is_arg ? <span className="text-slate-400 font-mono text-xs" title="Data probabilitas tidak tersedia">—</span> : formatProb(r.prob_month_above500, 50.0)}
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

        {/* 5. Pagination Bar matching DailyRainfallTable */}
        <div className="rainfall-pagination-bar">
          <div className="pagination-range-text">
            Menampilkan <strong>{filteredRows.length}</strong> dari <strong>{probRows.length}</strong> Stasiun Master
            {searchQuery && ` (disaring dari "${searchQuery}")`}
            {isLatestVintage ? ' &bull; Vintage Aktif Terbaru' : ' &bull; Vintage Historis'}
          </div>
          <div className="flex items-center space-x-2 text-xs text-slate-500">
            <span>Ambang Peringatan: PDKM (pb20) &gt; 70.0% &bull; PDCHT &gt; 50.0%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
