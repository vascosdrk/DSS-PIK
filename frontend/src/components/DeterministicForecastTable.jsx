import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search,
  RotateCcw,
  AlertCircle,
  CloudRain,
  UploadCloud,
  ShieldAlert,
  Calendar,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import './ProbabilityDataTable.css';

/**
 * DeterministicForecastTable
 * Tabel Prakiraan Deterministik ECMWF (satuan mm) untuk resolusi DASARIAN dan BULANAN.
 * Menggunakan sistem desain terpadu `prob-v2-*` agar konsisten dengan ProbabilityDataTable.
 */
export default function DeterministicForecastTable({
  resolutionMode = 'DASARIAN',
  onResolutionChange,
  onOpenIngestion,
  onOpenManagement,
  embeddedMode = false,
}) {
  const [periodsData, setPeriodsData] = useState({ dasarian: [], bulanan: [] });
  const [periodsList, setPeriodsList] = useState([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState('');
  const [selectedIssueDate, setSelectedIssueDate] = useState('');
  const [cutoffDate, setCutoffDate] = useState('');
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters State
  const [searchQuery, setSearchQuery] = useState('');
  const [kabupatenFilter, setKabupatenFilter] = useState('ALL');

  const normalizedRes = resolutionMode === 'BULANAN' ? 'BULANAN' : 'DASARIAN';

  // 1. Fetch available deterministic target periods from API
  const fetchAvailablePeriods = useCallback(() => {
    setLoading(true);
    setError(null);
    authFetch(API_ENDPOINTS.DETERMINISTIC_PERIODS)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat daftar periode deterministik`);
        return res.json();
      })
      .then((data) => {
        const dasList = data?.dasarian || [];
        const bulList = data?.bulanan || [];
        setPeriodsData({ dasarian: dasList, bulanan: bulList });
        const targetList = normalizedRes === 'BULANAN' ? bulList : dasList;
        setPeriodsList(targetList);

        if (targetList.length > 0) {
          setSelectedPeriodId((prev) =>
            targetList.some((p) => p.period_id === prev) ? prev : targetList[0].period_id
          );
        } else {
          setSelectedPeriodId('');
          setRows([]);
          setMeta(null);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch deterministic periods:', err);
        setError('Gagal memuat daftar periode prakiraan deterministik dari server.');
        setLoading(false);
      });
  }, [normalizedRes]);

  // Reset dependent filters cleanly whenever Resolusi Prakiraan changes
  useEffect(() => {
    setSelectedIssueDate('');
    setCutoffDate('');
    setKabupatenFilter('ALL');
    setSearchQuery('');
    fetchAvailablePeriods();
  }, [fetchAvailablePeriods]);

  // 2. Fetch deterministic data for selected period, vintage, and optional cutoff_date
  const fetchDeterministicData = useCallback(() => {
    if (!selectedPeriodId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    const params = {
      period_id: selectedPeriodId,
      resolution: normalizedRes,
      page: 1,
      page_size: 100,
    };
    if (selectedIssueDate) params.issue_date = selectedIssueDate;
    if (cutoffDate) params.cutoff_date = cutoffDate;

    authFetch(API_ENDPOINTS.DETERMINISTIC_DATA(params))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat data deterministik`);
        return res.json();
      })
      .then((data) => {
        setRows(data?.data || []);
        setMeta(data?.meta || null);
        if (!selectedIssueDate && data?.meta?.active_vintage_issue) {
          setSelectedIssueDate(data.meta.active_vintage_issue);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch deterministic data:', err);
        setError('Gagal memuat dataset prakiraan deterministik dari server.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedPeriodId, normalizedRes, selectedIssueDate, cutoffDate]);

  useEffect(() => {
    if (selectedPeriodId) {
      fetchDeterministicData();
    }
  }, [fetchDeterministicData, selectedPeriodId]);

  // Unique Kabupatens for dropdown
  const kabupatenList = useMemo(() => {
    const set = new Set();
    rows.forEach((r) => {
      if (r.kabupaten) set.add(r.kabupaten);
    });
    return Array.from(set).sort();
  }, [rows]);

  // Filtered rows sorted by kabupaten then station_name
  const filteredRows = useMemo(() => {
    const list = rows.filter((r) => {
      if (kabupatenFilter !== 'ALL' && r.kabupaten !== kabupatenFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchName = (r.station_name || '').toLowerCase().includes(q);
        const matchId = (r.station_id || '').toLowerCase().includes(q);
        const matchKab = (r.kabupaten || '').toLowerCase().includes(q);
        const matchCol = (r.source_column || '').toLowerCase().includes(q);
        if (!matchName && !matchId && !matchKab && !matchCol) return false;
      }
      return true;
    });

    return [...list].sort((a, b) => {
      const kabA = (a.kabupaten || '').localeCompare(b.kabupaten || '');
      if (kabA !== 0) return kabA;
      return (a.station_name || '').localeCompare(b.station_name || '');
    });
  }, [rows, kabupatenFilter, searchQuery]);

  const availableVintages = meta?.eligible_vintages || meta?.available_vintages || [];
  const activeIssue = meta?.active_vintage_issue || selectedIssueDate || null;
  const isLatestVintage =
    (meta?.available_vintages?.length || 0) > 0 && activeIssue === meta.available_vintages[0];
  const completeness = meta?.completeness || null;

  const handleResetFilters = () => {
    setSearchQuery('');
    setKabupatenFilter('ALL');
    setCutoffDate('');
    if (meta?.available_vintages?.length > 0) {
      setSelectedIssueDate(meta.available_vintages[0]);
    } else {
      setSelectedIssueDate('');
    }
  };

  const hasData = periodsList.length > 0 && rows.length > 0;

  return (
    <div className="prob-v2-page">
      {/* 1. Compact Operational Page Header (shown only when standalone) */}
      {!embeddedMode && (
      <div className="prob-v2-header">
        <div className="prob-v2-title-group">
          <div className="prob-v2-icon-box">
            <CloudRain size={20} />
          </div>
          <div>
            <div className="prob-v2-title-row">
              <h2 className="prob-v2-title">Tabel Prakiraan Deterministik ECMWF</h2>
              <span className="prob-v2-res-pill">{normalizedRes}</span>
              <span className="prob-v2-res-pill">SATUAN: MM</span>
            </div>
            <p className="prob-v2-desc">
              Prakiraan curah hujan deterministik (<strong>mm</strong>) 57 pos Kepulauan Riau · Prioritas kolom <strong>ADJUSTED</strong> di atas <strong>REGULAR</strong>
            </p>
          </div>
        </div>

        <div className="prob-v2-header-right">
          <div className="prob-v2-meta-cards">
            <div className="prob-v2-meta-card">
              <span className="prob-v2-meta-label">Kelengkapan Manual</span>
              <span className="prob-v2-meta-value font-mono">
                {completeness
                  ? `${completeness.manual_stations_available}/${completeness.manual_stations_total} (${completeness.completeness_pct}%)`
                  : '0/52 (0%)'}
              </span>
            </div>
            <div className="prob-v2-meta-card">
              <span className="prob-v2-meta-label">Penerbitan (Vintage)</span>
              <span className="prob-v2-meta-value font-mono">
                <span className={`prob-v2-status-dot ${isLatestVintage ? '' : 'historic'}`} />
                {activeIssue || 'Belum tersedia'}
              </span>
            </div>
          </div>

          <div className="prob-v2-actions">
            {onOpenIngestion && (
              <button
                type="button"
                className="prob-v2-btn-primary"
                onClick={() =>
                  onOpenIngestion(
                    normalizedRes === 'BULANAN' ? 'PROBABILITAS_BULANAN' : 'PROBABILITAS_DASARIAN'
                  )
                }
                title="Unggah workbook ECMWF (membaca data Probabilitas dan Deterministik secara terpadu)"
              >
                <UploadCloud size={15} />
                <span>Input / Pembaruan Data</span>
              </button>
            )}
            {onOpenManagement && (
              <button
                type="button"
                className="prob-v2-btn-secondary"
                onClick={() => onOpenManagement('CORRECTIONS', 'ENSMEAN')}
                title="Buka panel Kelola Vintage Deterministik (Pembatalan & Aktifkan Kembali)"
              >
                <ShieldAlert size={14} className="text-rose-600" />
                <span>Kelola Vintage</span>
              </button>
            )}
          </div>
        </div>
      </div>
      )}

      {/* 2. Unified Controls & Filter Toolbar */}
      <div className="prob-v2-controls-card">
        <div className="prob-v2-controls-top">
          {!embeddedMode ? (
          <div className="prob-v2-seg-wrap">
            <span className="prob-v2-seg-label">Resolusi Prakiraan</span>
            <div className="prob-v2-segmented" role="group" aria-label="Resolusi Prakiraan">
              <button
                type="button"
                className={`prob-v2-seg-btn ${normalizedRes === 'DASARIAN' ? 'active' : ''}`}
                onClick={() => onResolutionChange && onResolutionChange('DASARIAN')}
                aria-pressed={normalizedRes === 'DASARIAN'}
              >
                <span>Dasarian</span>
                <span className="prob-v2-seg-sub">({periodsData.dasarian.length} periode)</span>
              </button>
              <button
                type="button"
                className={`prob-v2-seg-btn ${normalizedRes === 'BULANAN' ? 'active' : ''}`}
                onClick={() => onResolutionChange && onResolutionChange('BULANAN')}
                aria-pressed={normalizedRes === 'BULANAN'}
              >
                <span>Bulanan</span>
                <span className="prob-v2-seg-sub">({periodsData.bulanan.length} periode)</span>
              </button>
            </div>
          </div>
          ) : (
          <div className="ecmwf-inline-title-row">
            <h3 className="ecmwf-inline-title">Tabel Prakiraan Deterministik ECMWF</h3>
            <span className="ecmwf-inline-meta font-mono">
              Kelengkapan:{' '}
              {completeness
                ? `${completeness.manual_stations_available}/${completeness.manual_stations_total} (${completeness.completeness_pct}%)`
                : '0/52 (0%)'}
            </span>
            <span className="ecmwf-inline-meta font-mono">
              <span className={`prob-v2-status-dot ${isLatestVintage ? '' : 'historic'}`} />
              Vintage: {activeIssue || 'Belum tersedia'}
            </span>
          </div>
          )}

          <div className="prob-v2-count-summary">
            Menampilkan <strong>{filteredRows.length}</strong> dari <strong>{rows.length}</strong> pos
          </div>
        </div>

        <div className="prob-v2-filter-row">
          <div className="prob-v2-field prob-v2-field-period">
            <label className="prob-v2-label" htmlFor="det-period-select">Periode Target</label>
            <select
              id="det-period-select"
              className="prob-v2-select font-mono"
              value={selectedPeriodId}
              disabled={periodsList.length === 0}
              onChange={(e) => {
                setSelectedPeriodId(e.target.value);
                setSelectedIssueDate('');
              }}
            >
              {periodsList.length === 0 ? (
                <option value="">Belum ada periode deterministik</option>
              ) : (
                periodsList.map((p) => (
                  <option key={p.period_id} value={p.period_id}>
                    {p.label || p.period_id} ({p.vintage_count} vintage)
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="prob-v2-field">
            <label className="prob-v2-label" htmlFor="det-vintage-select">Penerbitan (Vintage)</label>
            <select
              id="det-vintage-select"
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
                    {vDate} {idx === 0 && !cutoffDate ? '(Aktif)' : '(Historis)'}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="prob-v2-field">
            <label className="prob-v2-label" htmlFor="det-cutoff-input">
              Cutoff Evaluasi (Opsional)
            </label>
            <div className="prob-v2-search-box">
              <Calendar size={13} className="prob-v2-search-icon" />
              <input
                id="det-cutoff-input"
                type="date"
                className="prob-v2-input font-mono"
                value={cutoffDate}
                onChange={(e) => {
                  setCutoffDate(e.target.value);
                  setSelectedIssueDate('');
                }}
                title="Pilih tanggal cutoff untuk melihat vintage terbaru yang tersedia pada atau sebelum tanggal tersebut"
              />
            </div>
          </div>

          <div className="prob-v2-field">
            <label className="prob-v2-label" htmlFor="det-kab-select">Wilayah</label>
            <select
              id="det-kab-select"
              className="prob-v2-select"
              value={kabupatenFilter}
              onChange={(e) => setKabupatenFilter(e.target.value)}
              disabled={!hasData}
            >
              <option value="ALL">Semua Kabupaten/Kota</option>
              {kabupatenList.map((kab) => (
                <option key={kab} value={kab}>
                  {kab}
                </option>
              ))}
            </select>
          </div>

          <div className="prob-v2-field prob-v2-field-search">
            <label className="prob-v2-label" htmlFor="det-search-input">Cari Pos / ID / Kolom</label>
            <div className="prob-v2-search-box">
              <Search size={14} className="prob-v2-search-icon" />
              <input
                id="det-search-input"
                type="text"
                className="prob-v2-input"
                placeholder="Nama pos, ID stasiun, kabupaten..."
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
            title="Kembalikan semua filter ke pengaturan awal"
          >
            <RotateCcw size={14} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* 3. Main Data Table Card */}
      <div className="prob-v2-table-card">
        {error && (
          <div className="prob-v2-error" role="alert">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="prob-v2-loading">
            <div className="prob-v2-spinner" />
            <span>Memuat data prakiraan deterministik ({normalizedRes})...</span>
          </div>
        ) : periodsList.length === 0 ? (
          <div className="ensmean-empty-state">
            <div className="ensmean-empty-icon">
              <CloudRain size={22} />
            </div>
            <h3 className="ensmean-empty-title">
              Belum Ada Data Deterministik {normalizedRes === 'BULANAN' ? 'Bulanan' : 'Dasarian'} Tersimpan
            </h3>
            <p className="ensmean-empty-desc">
              Belum ada snapshot prakiraan deterministik aktif untuk resolusi{' '}
              <strong>{normalizedRes}</strong>. Unggah workbook ECMWF resmi melalui tombol{' '}
              <strong>Input / Pembaruan Data</strong> untuk memproses data <strong>Probabilitas (%)</strong> dan{' '}
              <strong>Deterministik (mm)</strong> secara bersamaan.
            </p>
            {onOpenIngestion && (
              <button
                type="button"
                className="prob-v2-btn-primary"
                style={{ marginTop: 8 }}
                onClick={() =>
                  onOpenIngestion(
                    normalizedRes === 'BULANAN' ? 'PROBABILITAS_BULANAN' : 'PROBABILITAS_DASARIAN'
                  )
                }
              >
                <UploadCloud size={15} />
                <span>Unggah Workbook ECMWF {normalizedRes === 'BULANAN' ? 'Bulanan' : 'Dasarian'}</span>
              </button>
            )}
          </div>
        ) : (
          <div className="prob-v2-scroll">
            <table className="prob-v2-table">
              <thead>
                <tr>
                  <th className="prob-v2-col-no col-center">No</th>
                  <th className="prob-v2-col-id">ID Pos</th>
                  <th className="prob-v2-col-name">Nama Pos Pengamatan</th>
                  <th>Kabupaten / Kota</th>
                  <th className="col-num col-pdcht">
                    Curah Hujan (mm)
                    <span className="prob-v2-th-sub">Prakiraan Deterministik</span>
                  </th>
                  <th className="col-center">Status Kolom</th>
                  <th>Kolom Sumber</th>
                  <th className="col-center">Issue Date</th>
                  <th>Berkas / Release Group</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: '28px 16px', color: '#64748b' }}>
                      Tidak ada pos pengamatan yang cocok dengan filter saat ini.
                    </td>
                  </tr>
                ) : (
                  filteredRows.map((r, idx) => (
                    <tr key={r.station_id}>
                      <td className="prob-v2-col-no col-center font-mono">{idx + 1}</td>
                      <td className="prob-v2-col-id font-mono font-semibold">{r.station_id}</td>
                      <td className="prob-v2-col-name font-semibold">
                        {r.station_name}
                        {r.is_arg && (
                          <span className="ensmean-badge ensmean-badge-arg" style={{ marginLeft: 6 }}>
                            ARG
                          </span>
                        )}
                      </td>
                      <td>{r.kabupaten || '—'}</td>
                      <td className="col-num">
                        {r.value_mm !== null && r.value_mm !== undefined ? (
                          <span className="ensmean-val-mm">
                            {Number(r.value_mm).toFixed(1)}
                            <span className="ensmean-val-unit">{r.unit || 'mm'}</span>
                          </span>
                        ) : (
                          <span className="prob-v2-val-empty">—</span>
                        )}
                      </td>
                      <td className="col-center">
                        {r.adjustment_status === 'ADJUSTED' ? (
                          <span className="ensmean-badge ensmean-badge-adjusted">ADJUSTED</span>
                        ) : r.adjustment_status === 'REGULAR' ? (
                          <span className="ensmean-badge ensmean-badge-regular">REGULAR</span>
                        ) : (
                          <span className="prob-v2-val-empty">—</span>
                        )}
                      </td>
                      <td className="font-mono" style={{ fontSize: '0.73rem', color: '#334155' }}>
                        {r.source_column || '—'}
                      </td>
                      <td className="col-center font-mono" style={{ fontSize: '0.73rem' }}>
                        {r.issue_date || '—'}
                      </td>
                      <td
                        className="font-mono"
                        style={{ fontSize: '0.71rem', color: '#64748b', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}
                        title={r.source_file || r.release_group_id || ''}
                      >
                        {r.release_group_id || r.source_file || '—'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Table Footer */}
        <div className="prob-v2-footer">
          <div className="prob-v2-footer-meta">
            <span>
              Resolusi: <strong>{normalizedRes}</strong>
            </span>
            <span>&middot;</span>
            <span>
              Periode: <strong className="font-mono">{selectedPeriodId || '—'}</strong>
            </span>
            {activeIssue && (
              <span className={`prob-v2-vintage-tag ${isLatestVintage ? '' : 'historic'}`}>
                <span className={`prob-v2-status-dot ${isLatestVintage ? '' : 'historic'}`} />
                Vintage {activeIssue} {isLatestVintage ? '(Aktif)' : '(Historis)'}
              </span>
            )}
            {cutoffDate && (
              <span className="prob-v2-vintage-tag historic">Cutoff &le; {cutoffDate}</span>
            )}
          </div>

          <div className="prob-v2-legend">
            <span className="prob-v2-legend-item">
              <span className="ensmean-badge ensmean-badge-adjusted">ADJUSTED</span>
              <span>{completeness?.adjusted_count ?? 0} pos</span>
            </span>
            <span className="prob-v2-legend-item">
              <span className="ensmean-badge ensmean-badge-regular">REGULAR</span>
              <span>{completeness?.regular_count ?? 0} pos</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
