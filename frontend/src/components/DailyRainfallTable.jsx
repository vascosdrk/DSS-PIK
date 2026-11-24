import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  Calendar, 
  ChevronLeft, 
  ChevronRight, 
  ChevronsLeft, 
  ChevronsRight, 
  Search, 
  RotateCcw, 
  Table as TableIcon,
  Download,
  AlertCircle,
  FileSpreadsheet,
  ArrowUpDown,
  PlusCircle,
  UploadCloud,
  Edit3,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import RainfallInputModal from './RainfallInputModal';

export default function DailyRainfallTable({ onOpenInfo, onOpenDownload, onOpenIngestion, onOpenManagement }) {
  const [columnsData, setColumnsData] = useState([]);
  const [tableRows, setTableRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showInputModal, setShowInputModal] = useState(false);

  // Filters State
  const [yearFilter, setYearFilter] = useState('2026');
  const [monthFilter, setMonthFilter] = useState('');
  const [dasarianFilter, setDasarianFilter] = useState('');
  const [startDateFilter, setStartDateFilter] = useState('');
  const [endDateFilter, setEndDateFilter] = useState('');
  const [sortOrder, setSortOrder] = useState('desc');

  // Pagination State
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(30);

  // Available Years (1981 - 2026)
  const availableYears = useMemo(() => {
    const list = [];
    for (let y = 2026; y >= 1981; y--) {
      list.push(y);
    }
    return list;
  }, []);

  // 1. Fetch column metadata once
  useEffect(() => {
    let isMounted = true;
    authFetch(API_ENDPOINTS.RAINFALL_COLUMNS)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat metadata kolom`);
        return res.json();
      })
      .then((data) => {
        if (isMounted && data && Array.isArray(data.station_columns)) {
          setColumnsData(data.station_columns);
        }
      })
      .catch((err) => {
        console.error('Failed to load rainfall columns:', err);
        if (isMounted) setError('Gagal memuat struktur kolom stasiun.');
      });

    return () => { isMounted = false; };
  }, []);

  // 2. Fetch table rows from MariaDB via backend API
  const fetchTableData = useCallback(() => {
    setLoading(true);
    setError(null);

    const params = {
      page,
      page_size: pageSize,
      order: sortOrder
    };

    if (yearFilter) params.year = yearFilter;
    if (monthFilter) params.month = monthFilter;
    if (dasarianFilter) params.dasarian = dasarianFilter;
    if (startDateFilter) params.start_date = startDateFilter;
    if (endDateFilter) params.end_date = endDateFilter;

    const url = API_ENDPOINTS.RAINFALL_DAILY_TABLE(params);

    authFetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat data observasi`);
        return res.json();
      })
      .then((data) => {
        setTableRows(data.data || []);
        setMeta(data.meta || null);
      })
      .catch((err) => {
        console.error('Failed to fetch daily rainfall table:', err);
        setError('Gagal memuat data observasi curah hujan dari database.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [page, pageSize, yearFilter, monthFilter, dasarianFilter, startDateFilter, endDateFilter, sortOrder]);

  useEffect(() => {
    fetchTableData();
  }, [fetchTableData]);

  // Compute Region Spans for Top Level Header
  const regionSpans = useMemo(() => {
    if (!columnsData.length) return [];
    const spans = [];
    let currentReg = null;
    let currentCount = 0;

    columnsData.forEach((col) => {
      const reg = col.region || 'LAINNYA';
      if (reg === currentReg) {
        currentCount++;
      } else {
        if (currentReg !== null) {
          spans.push({ region: currentReg, span: currentCount });
        }
        currentReg = reg;
        currentCount = 1;
      }
    });

    if (currentReg !== null) {
      spans.push({ region: currentReg, span: currentCount });
    }

    return spans;
  }, [columnsData]);

  const handleResetFilters = () => {
    setYearFilter('2026');
    setMonthFilter('');
    setDasarianFilter('');
    setStartDateFilter('');
    setEndDateFilter('');
    setSortOrder('desc');
    setPage(1);
  };

  const monthNames = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
  ];

  return (
    <div className="rainfall-table-page">
      {/* Page Title & Context Header */}
      <div className="rainfall-page-header">
        <div className="rainfall-page-title-group">
          <div className="rainfall-title-icon-box">
            <FileSpreadsheet size={24} className="text-forest" />
          </div>
          <div>
            <h2 className="rainfall-page-title">Tabel Data Curah Hujan Harian</h2>
          </div>
        </div>

        <div className="rainfall-header-meta">
          <div className="badge-meta-box">
            <span className="badge-meta-label">Total Tanggal Tersimpan</span>
            <span className="badge-meta-value">16.720 Hari (1981–2026)</span>
          </div>
          <div className="badge-meta-box">
            <span className="badge-meta-label">Cakupan Stasiun</span>
            <span className="badge-meta-value">{columnsData.length || 57} Stasiun</span>
          </div>
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              className="btn-input-rainfall-cta"
              onClick={() => (onOpenIngestion ? onOpenIngestion('CURAH_HUJAN') : setShowInputModal(true))}
              title="Buka modul input / pembaruan data curah hujan operasional"
            >
              <UploadCloud size={15} />
              <span>Input / Pembaruan Data CH</span>
            </button>
            {onOpenManagement && (
              <button
                type="button"
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-300 transition"
                onClick={() => onOpenManagement('CORRECTIONS', 'CURAH_HUJAN')}
                title="Buka formulir koreksi & pembatalan rekor curah hujan"
              >
                <Edit3 size={13} />
                <span>Koreksi &amp; Kelola CH</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Filter & Control Toolbar */}
      <div className="rainfall-toolbar">
        <div className="toolbar-filters-row">
          {/* Tahun Filter */}
          <div className="filter-item-group">
            <label className="filter-label">Tahun</label>
            <select
              className="toolbar-select"
              value={yearFilter}
              onChange={(e) => { setYearFilter(e.target.value); setPage(1); }}
            >
              <option value="">Semua Tahun</option>
              {availableYears.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {/* Bulan Filter */}
          <div className="filter-item-group">
            <label className="filter-label">Bulan</label>
            <select
              className="toolbar-select"
              value={monthFilter}
              onChange={(e) => { setMonthFilter(e.target.value); setPage(1); }}
            >
              <option value="">Semua Bulan</option>
              {monthNames.map((name, idx) => (
                <option key={idx + 1} value={idx + 1}>{name}</option>
              ))}
            </select>
          </div>

          {/* Dasarian Filter */}
          <div className="filter-item-group">
            <label className="filter-label">Dasarian</label>
            <select
              className="toolbar-select"
              value={dasarianFilter}
              onChange={(e) => { setDasarianFilter(e.target.value); setPage(1); }}
            >
              <option value="">Semua Dasarian</option>
              <option value="1">Dasarian I (Tgl 1–10)</option>
              <option value="2">Dasarian II (Tgl 11–20)</option>
              <option value="3">Dasarian III (Tgl 21–akhir)</option>
            </select>
          </div>

          {/* Tanggal Mulai & Akhir */}
          <div className="filter-item-group">
            <label className="filter-label">Mulai Tanggal</label>
            <input
              type="date"
              className="toolbar-input-date"
              value={startDateFilter}
              onChange={(e) => { setStartDateFilter(e.target.value); setPage(1); }}
            />
          </div>

          <div className="filter-item-group">
            <label className="filter-label">Sampai Tanggal</label>
            <input
              type="date"
              className="toolbar-input-date"
              value={endDateFilter}
              onChange={(e) => { setEndDateFilter(e.target.value); setPage(1); }}
            />
          </div>

          {/* Sort Order */}
          <div className="filter-item-group">
            <label className="filter-label">Urutan Tanggal</label>
            <button
              className="btn-sort-toggle"
              onClick={() => { setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc'); setPage(1); }}
              title="Ubah urutan tanggal"
            >
              <ArrowUpDown size={14} />
              <span>{sortOrder === 'desc' ? 'Terbaru ke Terlama' : 'Terlama ke Terbaru'}</span>
            </button>
          </div>

          {/* Reset Filters */}
          <div className="filter-item-group flex-end">
            <button className="btn-reset-toolbar" onClick={handleResetFilters} title="Kembalikan ke filter default">
              <RotateCcw size={14} />
              <span>Reset Filter</span>
            </button>
          </div>
        </div>

        {/* Legend / Status Indicators Bar */}
        <div className="rainfall-legend-bar">
          <div className="legend-items-left">
            <span className="legend-title">Petunjuk Nilai:</span>
            <div className="legend-chip">
              <span className="sample-cell rain-cell">12.5</span>
              <span>Hujan Terukur (&ge; 1.0 mm)</span>
            </div>
            <div className="legend-chip">
              <span className="sample-cell light-rain-cell">0.4</span>
              <span>Hujan Ringan (&lt; 1.0 mm)</span>
            </div>
            <div className="legend-chip">
              <span className="sample-cell zero-cell">-</span>
              <span>Tidak Ada Hujan (0 mm)</span>
            </div>
            <div className="legend-chip">
              <span className="sample-cell ttu-badge-sample">TTU</span>
              <span>Hujan Tidak Terukur (TTU)</span>
            </div>
            <div className="legend-chip">
              <span className="sample-cell missing-cell">9999</span>
              <span>Data Tidak Masuk / Kosong / Rusak</span>
            </div>
          </div>

          <div className="legend-items-right">
            {meta && (
              <span className="records-count-text">
                Menampilkan baris <strong>{((page - 1) * pageSize) + 1}</strong> – <strong>{Math.min(page * pageSize, meta.total_records)}</strong> dari <strong>{meta.total_records.toLocaleString('id-ID')}</strong> tanggal
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Main Table Area with Horizontal & Vertical Scrolling */}
      <div className="rainfall-table-container">
        {loading ? (
          <div className="table-loading-overlay">
            <div className="spin spinner-lg"></div>
            <span>Memuat data tabel dari MariaDB...</span>
          </div>
        ) : error ? (
          <div className="table-error-box">
            <AlertCircle size={24} className="text-red" />
            <div>
              <h4>Terjadi Kesalahan</h4>
              <p>{error}</p>
              <button className="btn-retry-sm" onClick={fetchTableData}>Coba Muat Ulang</button>
            </div>
          </div>
        ) : tableRows.length === 0 ? (
          <div className="table-empty-box">
            <Calendar size={32} className="text-muted" />
            <h4>Tidak Ada Data</h4>
            <p>Tidak ditemukan data observasi curah hujan pada rentang filter tanggal yang dipilih.</p>
            <button className="btn-reset-sm" onClick={handleResetFilters}>Reset Filter</button>
          </div>
        ) : (
          <div className="spreadsheet-wrapper">
            <table className="spreadsheet-table">
              <thead>
                {/* 1st Header Row: Grouping / Island Region Headers */}
                <tr className="header-row-regions">
                  <th colSpan="4" className="sticky-col sticky-header-group">
                    IDENTITAS WAKTU OBSERVASI
                  </th>
                  {regionSpans.map((r, i) => (
                    <th key={i} colSpan={r.span} className="region-group-th">
                      {r.region}
                    </th>
                  ))}
                </tr>

                {/* 2nd Header Row: Column Headers (Tahun, Bulan, Tanggal, Dasarian, and 58 Station Names) */}
                <tr className="header-row-columns">
                  <th className="sticky-col col-tahun" style={{ left: 0 }}>Tahun</th>
                  <th className="sticky-col col-bulan" style={{ left: 65 }}>Bulan</th>
                  <th className="sticky-col col-tanggal" style={{ left: 125 }}>Tgl</th>
                  <th className="sticky-col col-dasarian" style={{ left: 185 }}>Dasarian</th>

                  {columnsData.map((col, idx) => (
                    <th
                      key={idx}
                      className={`station-col-th ${onOpenInfo ? 'clickable-th' : ''} ${!col.in_master_57 ? 'th-non-master' : ''}`}
                      title={onOpenInfo ? `Klik untuk melihat Informasi Pos ${col.harian_name} (${col.station_id})` : `${col.harian_name} (${col.station_id})`}
                      onClick={() => {
                        if (onOpenInfo) onOpenInfo(col.station_id);
                      }}
                      style={{ cursor: onOpenInfo ? 'pointer' : 'default' }}
                    >
                      <div className="station-header-inner">
                        <span className="station-th-name">{col.harian_name}</span>
                        <span className="station-th-id font-mono">{col.station_id}</span>
                        {!col.in_master_57 && <span className="badge-non-master">Non-Master</span>}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {tableRows.map((row) => (
                  <tr key={row.date} className="spreadsheet-row">
                    {/* Sticky Date Columns */}
                    <td className="sticky-col col-tahun font-mono" style={{ left: 0 }}>{row.year}</td>
                    <td className="sticky-col col-bulan font-mono" style={{ left: 65 }}>{row.month}</td>
                    <td className="sticky-col col-tanggal font-mono" style={{ left: 125 }}>{row.day}</td>
                    <td className="sticky-col col-dasarian font-mono text-center" style={{ left: 185 }}>{row.dasarian}</td>

                    {/* 58 Station Rainfall Data Columns */}
                    {columnsData.map((col) => {
                      const sid = col.station_id;
                      const cellData = row.stations ? row.stations[sid] : null;

                      if (!cellData || cellData.obs_status === 'MISSING' || cellData.obs_status === 'DAMAGED' || cellData.obs_status === 'VOID' || cellData.rainfall_mm === null) {
                        return (
                          <td key={sid} className="data-cell cell-muted" title={`${col.harian_name} (${row.date}): Data Tidak Tersedia / Kosong / Alat Rusak (9999)`}>
                            <span className="cell-text-missing font-mono">9999</span>
                          </td>
                        );
                      }

                      if (cellData.obs_status === 'TTU') {
                        return (
                          <td key={sid} className="data-cell cell-ttu" title={`${col.harian_name} (${row.date}): Hujan Tidak Terukur (TTU)`}>
                            <span className="cell-badge-ttu">TTU</span>
                          </td>
                        );
                      }

                      const rf = cellData.rainfall_mm;
                      if (cellData.obs_status === 'OBSERVED_ZERO' || rf === 0.0) {
                        return (
                          <td key={sid} className="data-cell cell-zero" title={`${col.harian_name} (${row.date}): Tidak Ada Hujan (0 mm)`}>
                            <span className="cell-text-zero font-mono">-</span>
                          </td>
                        );
                      }

                      if (rf < 1.0) {
                        return (
                          <td key={sid} className="data-cell cell-light-rain" title={`${col.harian_name} (${row.date}): ${rf.toFixed(1)} mm`}>
                            <span className="cell-text-light-rain">{rf.toFixed(1)}</span>
                          </td>
                        );
                      }

                      // Significant rain >= 1.0 mm
                      const isHeavy = rf >= 20.0;
                      return (
                        <td key={sid} className={`data-cell cell-rain ${isHeavy ? 'cell-rain-heavy' : ''}`} title={`${col.harian_name} (${row.date}): ${rf.toFixed(1)} mm`}>
                          <span className={`cell-text-rain ${isHeavy ? 'font-bold' : ''}`}>{rf.toFixed(1)}</span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination Footer Controls */}
      {meta && meta.total_pages > 1 && (
        <div className="rainfall-pagination-bar">
          <div className="pagination-left">
            <span className="page-size-label">Baris per halaman:</span>
            <select
              className="page-size-select"
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
            >
              <option value={15}>15 baris</option>
              <option value={30}>30 baris</option>
              <option value={50}>50 baris</option>
              <option value={100}>100 baris</option>
            </select>
          </div>

          <div className="pagination-controls">
            <button
              className="btn-page-nav"
              disabled={page <= 1 || loading}
              onClick={() => setPage(1)}
              title="Halaman Pertama"
            >
              <ChevronsLeft size={16} />
            </button>
            <button
              className="btn-page-nav"
              disabled={page <= 1 || loading}
              onClick={() => setPage(prev => Math.max(1, prev - 1))}
              title="Halaman Sebelumnya"
            >
              <ChevronLeft size={16} />
            </button>

            <span className="page-indicator-text">
              Halaman <strong>{page}</strong> dari <strong>{meta.total_pages}</strong>
            </span>

            <button
              className="btn-page-nav"
              disabled={page >= meta.total_pages || loading}
              onClick={() => setPage(prev => Math.min(meta.total_pages, prev + 1))}
              title="Halaman Selanjutnya"
            >
              <ChevronRight size={16} />
            </button>
            <button
              className="btn-page-nav"
              disabled={page >= meta.total_pages || loading}
              onClick={() => setPage(meta.total_pages)}
              title="Halaman Terakhir"
            >
              <ChevronsRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Rainfall Input Modal */}
      <RainfallInputModal
        isOpen={showInputModal}
        onClose={() => setShowInputModal(false)}
        onSuccess={() => {
          fetchTableData();
        }}
      />
    </div>
  );
}
