import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Calendar, 
  ChevronLeft, 
  ChevronRight, 
  ChevronsLeft, 
  ChevronsRight, 
  Search, 
  RotateCcw, 
  Download, 
  Activity, 
  AlertCircle, 
  Layers, 
  SlidersHorizontal,
  Table as TableIcon,
  UploadCloud,
  Edit3,
  Cpu
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import { formatDateIndo } from '../utils/formatters';

export default function SpiDataTable({ onOpenDownload, onOpenIngestion, onOpenManagement, onOpenGenerator }) {
  // Main Switches: Period Type & Timescale
  const [periodType, setPeriodType] = useState('DASARIAN'); // 'DASARIAN' | 'DAILY'
  const [timescale, setTimescale] = useState('30D'); // '30D' | '90D'

  // Table Data State
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters State
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [stationSearch, setStationSearch] = useState('');
  const [order, setOrder] = useState('desc'); // 'desc' | 'asc'

  // Pagination State
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(30);

  // Fetch SPI Data
  const fetchSpiData = useCallback(() => {
    setLoading(true);
    setError(null);

    const params = {
      period_type: periodType,
      timescale: timescale,
      page,
      page_size: pageSize,
      order,
    };

    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    const url = API_ENDPOINTS.SPI_DATA(params);

    authFetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat data SPI`);
        return res.json();
      })
      .then((data) => {
        setColumns(data.columns || []);
        setRows(data.data || []);
        setMeta(data.meta || null);
      })
      .catch((err) => {
        console.error('Failed to fetch SPI data:', err);
        setError('Gagal memuat dataset SPI dari server.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [periodType, timescale, page, pageSize, order, startDate, endDate]);

  // Trigger fetch on parameter change
  useEffect(() => {
    fetchSpiData();
  }, [fetchSpiData]);

  // Reset page when switching mode or dates
  const handleSwitchPeriodType = (newType) => {
    if (newType !== periodType) {
      setPeriodType(newType);
      setPage(1);
    }
  };

  const handleSwitchTimescale = (newScale) => {
    if (newScale !== timescale) {
      setTimescale(newScale);
      setPage(1);
    }
  };

  const handleResetFilters = () => {
    setStartDate('');
    setEndDate('');
    setStationSearch('');
    setOrder('desc');
    setPage(1);
  };

  // Filter columns client-side based on station search
  const visibleColumns = useMemo(() => {
    if (!stationSearch.trim()) return columns;
    const q = stationSearch.toLowerCase().trim();
    return columns.filter(
      (c) =>
        c.station_name.toLowerCase().includes(q) ||
        c.station_id.toLowerCase().includes(q) ||
        (c.kabupaten && c.kabupaten.toLowerCase().includes(q))
    );
  }, [columns, stationSearch]);

  // Format cell value and color classification
  const formatPeriodDate = (dt, type, label) => {
    if (label && !label.includes('1970')) return label;
    if (!dt || dt.startsWith('1970')) return '-';
    if (type === 'BULANAN') {
      try {
        const parts = dt.split('-');
        if (parts.length >= 2) {
          const months = [
            'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
          ];
          const mIdx = parseInt(parts[1], 10) - 1;
          return `${months[mIdx] || parts[1]} ${parts[0]}`;
        }
      } catch {
        // fallback
      }
    }
    return formatDateIndo(dt);
  };

  const renderSpiCell = (val, isArg) => {
    if (isArg) {
      return (
        <span className="spi-cell spi-cell-arg" title="Data SPI tidak tersedia">
          — / Tidak tersedia
        </span>
      );
    }
    if (val === null || val === undefined) {
      return (
        <span className="spi-cell spi-cell-missing" title="Data SPI tidak tersedia">
          — / Tidak tersedia
        </span>
      );
    }

    const num = Number(val);
    let classSuffix = 'spi-normal';
    let label = 'Kondisi Normal';

    if (num <= -2.00) {
      classSuffix = 'spi-extreme-dry';
      label = 'Sangat Kering (≤ -2.00)';
    } else if (num <= -1.50) {
      classSuffix = 'spi-severe-dry';
      label = 'Kering Berat (-1.99 s.d. -1.50)';
    } else if (num <= -1.00) {
      classSuffix = 'spi-moderate-dry';
      label = 'Agak Kering (-1.49 s.d. -1.00)';
    } else if (num >= 2.00) {
      classSuffix = 'spi-extreme-wet';
      label = 'Sangat Basah (≥ +2.00)';
    } else if (num >= 1.50) {
      classSuffix = 'spi-severe-wet';
      label = 'Basah Berat (+1.50 s.d. +1.99)';
    } else if (num >= 1.00) {
      classSuffix = 'spi-moderate-wet';
      label = 'Agak Basah (+1.00 s.d. +1.49)';
    }

    return (
      <span className={`spi-cell ${classSuffix}`} title={`${label}: ${num.toFixed(2)}`}>
        {num >= 0 ? `+${num.toFixed(2)}` : num.toFixed(2)}
      </span>
    );
  };

  return (
    <div className="spi-data-table-container">
      {/* 1. Header & Primary Mode Switches */}
      <div className="spi-top-header">
        <div className="spi-header-left">
          <div className="spi-badge-pill">
            <Activity size={15} />
            <span>Standardized Precipitation Index</span>
          </div>
          <h2 className="spi-section-title">
            Data SPI — {periodType === 'DASARIAN' ? 'Resolusi Dasarian' : periodType === 'DAILY' ? 'Resolusi Harian' : 'Resolusi Bulanan'} {periodType !== 'BULANAN' ? `(${timescale === '30D' ? 'Akumulasi 30 Hari' : 'Akumulasi 90 Hari'})` : '(Akumulasi 1 Bulan)'}
          </h2>
          <p className="spi-section-desc">
            {periodType === 'DASARIAN' && (
              <>Monitoring indeks kekeringan meteorologis 57 titik stasiun Kepri. Decision Engine PDKM aktif menggunakan <strong>SPI Dasarian 30d</strong>.</>
            )}
            {periodType === 'DAILY' && (
              <>Monitoring indeks kekeringan harian real-time untuk analisis pergerakan dinamis akumulasi 30 hari &amp; 90 hari.</>
            )}
            {periodType === 'BULANAN' && (
              <>Monitoring indeks kekeringan skala bulanan historis &amp; klimatologis Kepulauan Riau (57 stasiun).</>
            )}
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2 mt-2 sm:mt-0 shrink-0">
          {onOpenGenerator && (
            <button
              type="button"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-purple-700 hover:bg-purple-800 text-white text-xs font-bold rounded-lg shadow-sm transition"
              onClick={() => onOpenGenerator(periodType, timescale)}
              title="Perhitungan nilai SPI manual dari data curah hujan harian MariaDB berbasis distribusi konsensus terbaik"
            >
              <Cpu size={14} />
              <span>Generator SPI</span>
            </button>
          )}
          {onOpenIngestion && (
            <button
              type="button"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-700 hover:bg-indigo-800 text-white text-xs font-semibold rounded-lg shadow-sm transition"
              onClick={() => onOpenIngestion(periodType === 'BULANAN' ? 'SPI_BULANAN' : periodType === 'DAILY' ? 'SPI_HARIAN' : 'SPI_DASARIAN')}
              title="Buka modul upload file Parquet / Excel SPI"
            >
              <UploadCloud size={14} />
              <span>Input / Pembaruan SPI</span>
            </button>
          )}
          {onOpenManagement && (
            <button
              type="button"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-300 transition"
              onClick={() => onOpenManagement('CORRECTIONS', 'SPI')}
              title="Buka panel kelola & void SPI"
            >
              <Edit3 size={13} />
              <span>Kelola / Pembatalan SPI</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Switch Controls Bar: Resolution & Timescale */}
      <div className="spi-controls-card">
        <div className="spi-switch-group">
          <div className="switch-item">
            <span className="switch-label">Resolusi Waktu:</span>
            <div className="segmented-switch" role="group" aria-label="Resolusi SPI">
              <button
                type="button"
                className={`switch-btn ${periodType === 'DASARIAN' ? 'active' : ''}`}
                onClick={() => handleSwitchPeriodType('DASARIAN')}
              >
                SPI DASARIAN
              </button>
              <button
                type="button"
                className={`switch-btn ${periodType === 'DAILY' ? 'active' : ''}`}
                onClick={() => handleSwitchPeriodType('DAILY')}
              >
                SPI HARIAN
              </button>
              <button
                type="button"
                className={`switch-btn ${periodType === 'BULANAN' ? 'active' : ''}`}
                onClick={() => handleSwitchPeriodType('BULANAN')}
              >
                SPI BULANAN
              </button>
            </div>
          </div>

          <div className="switch-item">
            <span className="switch-label">Periode Akumulasi:</span>
            {periodType === 'BULANAN' ? (
              <div className="segmented-switch" role="group" aria-label="Timescale SPI">
                <button type="button" className="switch-btn active" disabled>
                  1 Bulan (Standar)
                </button>
              </div>
            ) : (
              <div className="segmented-switch" role="group" aria-label="Timescale SPI">
                <button
                  type="button"
                  className={`switch-btn ${timescale === '30D' ? 'active' : ''}`}
                  onClick={() => handleSwitchTimescale('30D')}
                >
                  30 Hari (30d)
                </button>
                <button
                  type="button"
                  className={`switch-btn ${timescale === '90D' ? 'active' : ''}`}
                  onClick={() => handleSwitchTimescale('90D')}
                >
                  90 Hari (90d)
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Filters Row */}
        <div className="spi-filters-row">
          <div className="filter-input-wrap">
            <label className="filter-tiny-label">Mulai Tanggal</label>
            <input
              type="date"
              className="spi-filter-date"
              value={startDate}
              onChange={(e) => { setStartDate(e.target.value); setPage(1); }}
            />
          </div>

          <div className="filter-input-wrap">
            <label className="filter-tiny-label">Sampai Tanggal</label>
            <input
              type="date"
              className="spi-filter-date"
              value={endDate}
              onChange={(e) => { setEndDate(e.target.value); setPage(1); }}
            />
          </div>

          <div className="filter-input-wrap search-stn-wrap">
            <label className="filter-tiny-label">Cari Stasiun Kolom</label>
            <div className="spi-search-inner">
              <Search size={13} className="spi-search-icon" />
              <input
                type="text"
                placeholder="Nama stasiun, ID, kabupaten..."
                className="spi-search-input"
                value={stationSearch}
                onChange={(e) => setStationSearch(e.target.value)}
              />
              {stationSearch && (
                <button
                  type="button"
                  className="spi-clear-btn"
                  onClick={() => setStationSearch('')}
                >
                  &times;
                </button>
              )}
            </div>
          </div>

          <div className="filter-input-wrap">
            <label className="filter-tiny-label">Urutan</label>
            <select
              className="spi-filter-select"
              value={order}
              onChange={(e) => { setOrder(e.target.value); setPage(1); }}
            >
              <option value="desc">Tanggal Terbaru ke Terlama</option>
              <option value="asc">Tanggal Terlama ke Terbaru</option>
            </select>
          </div>

          <div className="filter-input-wrap flex-end">
            <button
              type="button"
              className="btn-reset-spi"
              onClick={handleResetFilters}
              title="Reset filter tanggal dan pencarian"
            >
              <RotateCcw size={13} />
              <span>Reset</span>
            </button>
          </div>
        </div>
      </div>

      {/* 3. Legend Bar */}
      <div className="spi-legend-bar">
        <span className="spi-legend-title">Klasifikasi Indeks SPI:</span>
        <div className="spi-legend-chips">
          <span className="spi-chip chip-ext-dry">&le; -2.00 (AWAS / Sangat Kering)</span>
          <span className="spi-chip chip-sev-dry">-1.99 s.d. -1.50 (SIAGA / Kering)</span>
          <span className="spi-chip chip-mod-dry">-1.49 s.d. -1.00 (WASPADA / Agak Kering)</span>
          <span className="spi-chip chip-norm">-0.99 s.d. +0.99 (Normal)</span>
          <span className="spi-chip chip-mod-wet">+1.00 s.d. +1.49 (Agak Basah)</span>
          <span className="spi-chip chip-sev-wet">&ge; +1.50 (Sangat Basah)</span>
          <span className="spi-chip chip-miss">— (Tidak tersedia)</span>
        </div>
      </div>

      {/* 4. Main Spreadsheet Table */}
      <div className="spi-table-wrapper">
        {loading && (
          <div className="table-loading-overlay">
            <div className="spin spinner-lg"></div>
            <span>Memuat tabel SPI ({periodType} {timescale})...</span>
          </div>
        )}

        {error && (
          <div className="table-error-banner">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && (
          <table className="spi-spreadsheet-table">
            <thead>
              <tr>
                <th className="th-sticky-date">Tanggal / Periode</th>
                {visibleColumns.map((col) => (
                  <th key={col.station_id} className="th-station-col" title={`${col.station_name} (${col.kabupaten})`}>
                    <div className="th-stn-inner">
                      <span className="th-stn-name">{col.station_name}</span>
                      <span className="th-stn-id font-mono">{col.station_id}</span>
                      
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={visibleColumns.length + 1} className="td-empty-table">
                    Tidak ada catatan SPI yang memenuhi kriteria filter.
                  </td>
                </tr>
              ) : (
                rows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    <td className="td-sticky-date font-mono font-medium">
                      {formatPeriodDate(row.date, periodType, row.period_label)}
                    </td>
                    {visibleColumns.map((col) => {
                      const val = row.stations ? row.stations[col.station_id] : null;
                      return (
                        <td key={col.station_id} className="text-center font-mono font-medium">
                          {renderSpiCell(val, col.is_arg)}
                        </td>
                      );
                    })}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* 5. Pagination Bar */}
      {meta && (
        <div className="table-pagination-bar">
          <div className="pagination-info">
            Menampilkan halaman <strong>{meta.page}</strong> dari <strong>{meta.total_pages}</strong> ({meta.total_records.toLocaleString('id-ID')} catatan total)
          </div>

          <div className="pagination-buttons">
            <button
              type="button"
              className="btn-page"
              onClick={() => setPage(1)}
              disabled={meta.page <= 1}
              title="Halaman Pertama"
            >
              <ChevronsLeft size={15} />
            </button>
            <button
              type="button"
              className="btn-page"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={meta.page <= 1}
              title="Halaman Sebelumnya"
            >
              <ChevronLeft size={15} />
            </button>

            <span className="page-indicator font-mono">
              {meta.page} / {meta.total_pages}
            </span>

            <button
              type="button"
              className="btn-page"
              onClick={() => setPage((p) => Math.min(meta.total_pages, p + 1))}
              disabled={meta.page >= meta.total_pages}
              title="Halaman Berikutnya"
            >
              <ChevronRight size={15} />
            </button>
            <button
              type="button"
              className="btn-page"
              onClick={() => setPage(meta.total_pages)}
              disabled={meta.page >= meta.total_pages}
              title="Halaman Terakhir"
            >
              <ChevronsRight size={15} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
