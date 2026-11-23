import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  X,
  Calendar,
  Search,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  FileSpreadsheet,
  Save,
  RotateCcw,
  Sparkles,
  Info,
  Clock,
  Layers,
  ChevronRight,
  ArrowRight,
  Check,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';
import { formatDateIndo } from '../utils/formatters';

export default function RainfallInputModal({ isOpen, onClose, onSuccess }) {
  const [mode, setMode] = useState('DAILY'); // 'DAILY' | 'DASARIAN'
  const [step, setStep] = useState('INPUT'); // 'INPUT' | 'PREVIEW' | 'RESULT'

  // Master Stations
  const [stations, setStations] = useState([]);
  const [stationsLoading, setStationsLoading] = useState(true);
  const [stationsError, setStationsError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Mode 1: Daily State
  const [dailyDate, setDailyDate] = useState(() => {
    const today = new Date();
    // Default to yesterday or today in YYYY-MM-DD
    return today.toISOString().split('T')[0];
  });
  // Map of station_id -> { value: string, type: 'NUMERIC' | 'ZERO' | 'TTU' | 'MISSING' | '' }
  const [dailyInputs, setDailyInputs] = useState({});
  const [dailyCurrentValues, setDailyCurrentValues] = useState({});

  // Mode 2: Dasarian State
  const [dasarianYear, setDasarianYear] = useState('2026');
  const [dasarianMonth, setDasarianMonth] = useState('9'); // September
  const [dasarianNumber, setDasarianNumber] = useState('3'); // Dasarian 3
  // Map of `${station_id}_${date}` -> string value
  const [dasarianInputs, setDasarianInputs] = useState({});
  const [dasarianCurrentValues, setDasarianCurrentValues] = useState({});

  // Preview & Commit State
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [confirmOverwrite, setConfirmOverwrite] = useState(false);
  const [correctionReason, setCorrectionReason] = useState('Input data observasi manual operasional');
  const [operatorName, setOperatorName] = useState('OPERATOR_CEWS');
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitResult, setCommitResult] = useState(null);

  // 1. Fetch master stations with retry capability
  const fetchStations = useCallback(() => {
    setStationsLoading(true);
    setStationsError(null);
    const endpoint = API_ENDPOINTS.STATIONS_MASTER || API_ENDPOINTS.RAINFALL_INPUT_STATIONS;
    authFetch(endpoint)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memuat daftar stasiun master`);
        return res.json();
      })
      .then((data) => {
        if (!data || !Array.isArray(data.stations) || data.stations.length === 0) {
          throw new Error('Daftar stasiun master kosong atau tidak valid.');
        }
        setStations(data.stations);
        setStationsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch stations for input:', err);
        setStationsError(err.message || 'Gagal memuat daftar stasiun master');
        setStationsLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    fetchStations();
  }, [isOpen, fetchStations]);

  // 2. Compute Dasarian Dates
  const dasarianDates = useMemo(() => {
    const y = parseInt(dasarianYear, 10);
    const m = parseInt(dasarianMonth, 10);
    const das = parseInt(dasarianNumber, 10);
    if (!y || !m || !das) return [];

    let startDay = 1;
    let endDay = 10;
    if (das === 2) {
      startDay = 11;
      endDay = 20;
    } else if (das === 3) {
      startDay = 21;
      // Get last calendar day of month m (handles February & leap years)
      endDay = new Date(y, m, 0).getDate();
    }

    const dates = [];
    for (let d = startDay; d <= endDay; d++) {
      const padM = String(m).padStart(2, '0');
      const padD = String(d).padStart(2, '0');
      dates.push(`${y}-${padM}-${padD}`);
    }
    return dates;
  }, [dasarianYear, dasarianMonth, dasarianNumber]);

  // 3. Fetch Current Values for Daily Date
  const fetchDailyCurrentValues = useCallback(() => {
    if (!dailyDate) return;
    authFetch(API_ENDPOINTS.RAINFALL_INPUT_CURRENT_VALUES(dailyDate, dailyDate))
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => {
        if (json && json.data) {
          setDailyCurrentValues(json.data);
        } else {
          setDailyCurrentValues({});
        }
      })
      .catch(() => setDailyCurrentValues({}));
  }, [dailyDate]);

  useEffect(() => {
    if (isOpen && mode === 'DAILY') {
      fetchDailyCurrentValues();
    }
  }, [isOpen, mode, fetchDailyCurrentValues]);

  // 4. Fetch Current Values for Dasarian Dates
  const fetchDasarianCurrentValues = useCallback(() => {
    if (!dasarianDates.length) return;
    const sDate = dasarianDates[0];
    const eDate = dasarianDates[dasarianDates.length - 1];
    authFetch(API_ENDPOINTS.RAINFALL_INPUT_CURRENT_VALUES(sDate, eDate))
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => {
        if (json && json.data) {
          setDasarianCurrentValues(json.data);
        } else {
          setDasarianCurrentValues({});
        }
      })
      .catch(() => setDasarianCurrentValues({}));
  }, [dasarianDates]);

  useEffect(() => {
    if (isOpen && mode === 'DASARIAN' && dasarianDates.length > 0) {
      fetchDasarianCurrentValues();
    }
  }, [isOpen, mode, dasarianDates, fetchDasarianCurrentValues]);

  // Reset inputs on modal close
  const handleModalClose = () => {
    setStep('INPUT');
    setPreviewData(null);
    setCommitResult(null);
    setConfirmOverwrite(false);
    onClose();
  };

  // Filtered stations for display
  const filteredStations = useMemo(() => {
    if (!searchTerm.trim()) return stations;
    const q = searchTerm.toLowerCase();
    return stations.filter(
      (s) =>
        (s.station_name && s.station_name.toLowerCase().includes(q)) ||
        (s.station_id && s.station_id.toLowerCase().includes(q)) ||
        (s.kabupaten && s.kabupaten.toLowerCase().includes(q)) ||
        (s.regency && s.regency.toLowerCase().includes(q)) ||
        (s.station_type && s.station_type.toLowerCase().includes(q))
    );
  }, [stations, searchTerm]);

  // Parse raw text value into structured entry
  const parseInputValue = (val) => {
    if (val === undefined || val === null) return null;
    const str = String(val).trim();
    if (str === '') return null; // Untouched / Empty

    const upper = str.toUpperCase();
    if (upper === 'TTU' || upper === 'T') {
      return { rainfall_mm: 0.0, obs_status: 'TTU', original_symbol: 'TTU' };
    }
    if (upper === '-' || upper === '0' || upper === '0.0' || upper === '0.00' || upper === 'NIHIL') {
      return { rainfall_mm: 0.0, obs_status: 'OBSERVED_ZERO', original_symbol: '-' };
    }
    if (upper === 'X' || upper === 'MISSING') {
      return { rainfall_mm: null, obs_status: 'MISSING', original_symbol: 'X' };
    }

    const num = parseFloat(str.replace(',', '.'));
    if (!isNaN(num) && isFinite(num)) {
      if (num < 0) {
        return { rainfall_mm: num, obs_status: 'OBSERVED_VALID', original_symbol: str }; // will fail validation
      }
      if (num === 0) {
        return { rainfall_mm: 0.0, obs_status: 'OBSERVED_ZERO', original_symbol: '0.0' };
      }
      return { rainfall_mm: num, obs_status: 'OBSERVED_VALID', original_symbol: str };
    }

    // Invalid string
    return { rainfall_mm: null, obs_status: 'INVALID', original_symbol: str };
  };

  // Collect all filled entries based on active mode
  const collectEntries = () => {
    const entries = [];
    if (mode === 'DAILY') {
      Object.entries(dailyInputs).forEach(([sid, val]) => {
        const parsed = parseInputValue(val);
        if (parsed !== null) {
          entries.push({
            station_id: sid,
            observation_date: dailyDate,
            rainfall_mm: parsed.rainfall_mm,
            obs_status: parsed.obs_status,
            original_symbol: parsed.original_symbol,
          });
        }
      });
    } else {
      // DASARIAN mode
      Object.entries(dasarianInputs).forEach(([key, val]) => {
        const [sid, dt] = key.split('_');
        if (sid && dt) {
          const parsed = parseInputValue(val);
          if (parsed !== null) {
            entries.push({
              station_id: sid,
              observation_date: dt,
              rainfall_mm: parsed.rainfall_mm,
              obs_status: parsed.obs_status,
              original_symbol: parsed.original_symbol,
            });
          }
        }
      });
    }
    return entries;
  };

  // Handle Validate & Preview click
  const handleValidatePreview = () => {
    if (stationsLoading || stationsError || stations.length === 0) {
      alert('Daftar stasiun master belum berhasil dimuat. Silakan klik tombol Muat Ulang.');
      return;
    }
    const entries = collectEntries();
    if (entries.length === 0) {
      alert('Belum ada data curah hujan yang diisi pada formulir.');
      return;
    }

    setPreviewLoading(true);
    authFetch(API_ENDPOINTS.RAINFALL_INPUT_PREVIEW, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, entries }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Gagal memvalidasi data`);
        return res.json();
      })
      .then((data) => {
        setPreviewData(data);
        setConfirmOverwrite(false);
        setStep('PREVIEW');
        setPreviewLoading(false);
      })
      .catch((err) => {
        console.error('Validation preview failed:', err);
        alert(`Gagal melakukan validasi data: ${err.message}`);
        setPreviewLoading(false);
      });
  };

  // Handle Commit to MariaDB
  const handleCommit = () => {
    if (!previewData || !previewData.items) return;
    const entries = collectEntries();

    if (previewData.total_diff > 0 && !confirmOverwrite) {
      alert('Harap centang konfirmasi penimpaan/koreksi data terlebih dahulu.');
      return;
    }

    const batchId = `BATCH_MANUAL_${new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14)}`;

    setCommitLoading(true);
    authFetch(API_ENDPOINTS.RAINFALL_INPUT_COMMIT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        batch_id: batchId,
        entries,
        confirm_overwrite: confirmOverwrite,
        correction_reason: correctionReason,
        approved_by: operatorName,
      }),
    })
      .then((res) => {
        if (!res.ok) return res.json().then((err) => Promise.reject(err));
        return res.json();
      })
      .then((result) => {
        setCommitResult(result);
        setStep('RESULT');
        setCommitLoading(false);
        if (onSuccess) {
          onSuccess();
        }
      })
      .catch((err) => {
        console.error('Commit failed:', err);
        alert(`Gagal menyimpan data ke MariaDB: ${err.detail || err.message}`);
        setCommitLoading(false);
      });
  };

  // Helper for quick fills in Daily Mode
  const handleDailyQuickSet = (sid, val) => {
    setDailyInputs((prev) => ({ ...prev, [sid]: val }));
  };

  const handleDailyFillAllZero = () => {
    const updated = { ...dailyInputs };
    filteredStations.forEach((s) => {
      if (updated[s.station_id] === undefined || updated[s.station_id] === '') {
        updated[s.station_id] = '0';
      }
    });
    setDailyInputs(updated);
  };

  const handleDailyClearAll = () => {
    setDailyInputs({});
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog rainfall-input-dialog">
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-header-left">
            <div className="flex-align gap-2">
              <FileSpreadsheet size={20} className="text-forest" />
              <h3 className="modal-title">Form Input Data Curah Hujan DSS-PIK</h3>
            </div>
            <p className="modal-subtitle">
              Input observasi harian dan dasarian langsung ke MariaDB dengan audit &amp; proteksi integritas data.
            </p>
          </div>

          <div className="flex-align gap-3">
            {step === 'INPUT' && (
              <div className="input-mode-toggle">
                <button
                  type="button"
                  className={`btn-mode-tab ${mode === 'DAILY' ? 'active' : ''}`}
                  onClick={() => {
                    setMode('DAILY');
                    setSearchTerm('');
                  }}
                >
                  <Calendar size={13} />
                  <span>Input Harian</span>
                </button>
                <button
                  type="button"
                  className={`btn-mode-tab ${mode === 'DASARIAN' ? 'active' : ''}`}
                  onClick={() => {
                    setMode('DASARIAN');
                    setSearchTerm('');
                  }}
                >
                  <Layers size={13} />
                  <span>Input Satu Dasarian</span>
                </button>
              </div>
            )}

            <button className="btn-modal-close" onClick={handleModalClose} title="Tutup">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="modal-body rainfall-input-body">
          {/* STEP 1: INPUT FORM */}
          {step === 'INPUT' && (
            <div className="rainfall-input-flow">
              {/* Parameters Toolbar */}
              <div className="input-controls-bar">
                {mode === 'DAILY' ? (
                  <div className="input-param-row">
                    <div className="input-param-item">
                      <label className="param-label">
                        <Calendar size={13} className="inline-icon text-muted" />
                        Tanggal Pengamatan:
                      </label>
                      <input
                        type="date"
                        className="input-date-styled"
                        value={dailyDate}
                        onChange={(e) => setDailyDate(e.target.value)}
                        max={new Date().toISOString().split('T')[0]}
                      />
                    </div>

                    <div className="input-search-item">
                      <div className="search-input-wrapper">
                        <Search size={14} className="search-icon-inside" />
                        <input
                          type="text"
                          className="filter-input search-input-styled"
                          placeholder="Cari stasiun atau kabupaten..."
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                        />
                        {searchTerm && (
                          <button className="btn-clear-search" onClick={() => setSearchTerm('')}>
                            &times;
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="input-quick-actions">
                      <button
                        type="button"
                        className="btn-quick-action"
                        onClick={handleDailyFillAllZero}
                        title="Isi 0 mm (Nihil) untuk semua stasiun yang belum diisi"
                      >
                        Set Kosong jadi 0 mm
                      </button>
                      <button
                        type="button"
                        className="btn-quick-action outline"
                        onClick={handleDailyClearAll}
                      >
                        Kosongkan Form
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="input-param-row">
                    <div className="input-param-item">
                      <label className="param-label">Tahun:</label>
                      <select
                        className="input-select-styled"
                        value={dasarianYear}
                        onChange={(e) => setDasarianYear(e.target.value)}
                      >
                        {[2026, 2025, 2024, 2023, 2022, 2021, 2020].map((y) => (
                          <option key={y} value={y}>
                            {y}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="input-param-item">
                      <label className="param-label">Bulan:</label>
                      <select
                        className="input-select-styled"
                        value={dasarianMonth}
                        onChange={(e) => setDasarianMonth(e.target.value)}
                      >
                        {[
                          'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                          'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
                        ].map((name, idx) => (
                          <option key={idx + 1} value={idx + 1}>
                            {name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="input-param-item">
                      <label className="param-label">Dasarian:</label>
                      <select
                        className="input-select-styled"
                        value={dasarianNumber}
                        onChange={(e) => setDasarianNumber(e.target.value)}
                      >
                        <option value="1">Dasarian I (Tgl 1–10)</option>
                        <option value="2">Dasarian II (Tgl 11–20)</option>
                        <option value="3">Dasarian III (Tgl 21–Akhir Bulan)</option>
                      </select>
                    </div>

                    <div className="input-search-item">
                      <div className="search-input-wrapper">
                        <Search size={14} className="search-icon-inside" />
                        <input
                          type="text"
                          className="filter-input search-input-styled"
                          placeholder="Cari stasiun..."
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="dasarian-date-range-badge">
                      <Calendar size={12} className="inline-icon" />
                      <span>
                        {dasarianDates.length > 0
                          ? `${dasarianDates[0]} s/d ${dasarianDates[dasarianDates.length - 1]} (${dasarianDates.length} hari)`
                          : ''}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Instructions Banner */}
              <div className="input-help-banner">
                <Info size={14} className="inline-icon text-forest" />
                <span className="text-2xs text-secondary">
                  <strong>Panduan Input:</strong> Masukkan angka positif untuk CH terukur (misal: <code>15.5</code>), <code>0</code> atau <code>-</code> untuk hari tanpa hujan, <code>TTU</code> untuk jejak hujan (&lt;0.5 mm), atau biarkan kosong jika belum ada data. Sel kosong tidak akan disimpan sebagai 0 mm.
                </span>
              </div>

              {/* Table / Spreadsheet Container */}
              {stationsLoading ? (
                <div className="input-loading-box">
                  <div className="spin spinner-md"></div>
                  <span>Memuat daftar 57 stasiun master...</span>
                </div>
              ) : stationsError ? (
                <div className="input-error-box">
                  <div className="flex-align gap-2">
                    <AlertCircle size={18} className="text-red flex-shrink-0" />
                    <span>{stationsError}</span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-xs btn-outline"
                    onClick={fetchStations}
                    style={{ marginLeft: 'auto' }}
                  >
                    <RotateCcw size={12} className="inline-icon" />
                    Muat Ulang
                  </button>
                </div>
              ) : stations.length === 0 ? (
                <div className="input-error-box">
                  <AlertCircle size={18} className="text-amber flex-shrink-0" />
                  <span>Tidak ada stasiun master yang ditemukan.</span>
                  <button
                    type="button"
                    className="btn btn-xs btn-outline"
                    onClick={fetchStations}
                    style={{ marginLeft: 'auto' }}
                  >
                    <RotateCcw size={12} className="inline-icon" />
                    Muat Ulang
                  </button>
                </div>
              ) : mode === 'DAILY' ? (
                /* MODE 1: DAILY TABLE */
                <div className="daily-input-table-wrapper">
                  <table className="daily-input-table">
                    <thead>
                      <tr>
                        <th style={{ width: '45px' }}>No</th>
                        <th style={{ width: '110px' }}>ID Stasiun</th>
                        <th>Nama Stasiun</th>
                        <th>Kabupaten</th>
                        <th style={{ width: '130px' }}>Data di DB</th>
                        <th style={{ width: '160px' }}>Nilai Input CH (mm)</th>
                        <th style={{ width: '180px' }}>Opsi Cepat</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredStations.map((stn, idx) => {
                        const sid = stn.station_id;
                        const currentDb = dailyCurrentValues[sid]?.[dailyDate];
                        const inputValue = dailyInputs[sid] !== undefined ? dailyInputs[sid] : '';
                        const isFilled = inputValue !== '';

                        return (
                          <tr key={sid} className={isFilled ? 'row-input-filled' : 'row-input-empty'}>
                            <td className="text-center font-mono text-xs">{idx + 1}</td>
                            <td className="font-mono font-bold text-xs">{sid}</td>
                            <td>
                              <div className="flex-align gap-1">
                                <span className="font-semibold text-xs">{stn.station_name}</span>

                              </div>
                              {stn.region && (
                                <span className="text-3xs text-muted font-mono">({stn.region})</span>
                              )}
                            </td>
                            <td className="text-xs text-muted">{stn.kabupaten || stn.regency}</td>
                            <td>
                              {currentDb ? (
                                <span className={`badge-pill-db ${currentDb.obs_status === 'OBSERVED_ZERO' ? 'badge-db-zero' : currentDb.obs_status === 'TTU' ? 'badge-db-ttu' : 'badge-db-rain'}`}>
                                  {currentDb.obs_status === 'TTU'
                                    ? 'TTU'
                                    : `${currentDb.rainfall_mm !== null ? currentDb.rainfall_mm.toFixed(1) : '-'} mm`}
                                </span>
                              ) : (
                                <span className="text-3xs text-muted font-mono">Belum ada</span>
                              )}
                            </td>
                            <td>
                              <input
                                type="text"
                                className={`input-cell-daily ${isFilled ? 'filled' : ''}`}
                                placeholder="Kosong"
                                value={inputValue}
                                onChange={(e) => handleDailyQuickSet(sid, e.target.value)}
                              />
                            </td>
                            <td>
                              <div className="flex-align gap-1">
                                <button
                                  type="button"
                                  className="btn-opt-pill zero"
                                  onClick={() => handleDailyQuickSet(sid, '0')}
                                  title="Isi Nihil 0 mm"
                                >
                                  0 mm
                                </button>
                                <button
                                  type="button"
                                  className="btn-opt-pill ttu"
                                  onClick={() => handleDailyQuickSet(sid, 'TTU')}
                                  title="Isi Jejak Hujan TTU"
                                >
                                  TTU
                                </button>
                                {isFilled && (
                                  <button
                                    type="button"
                                    className="btn-opt-pill clear"
                                    onClick={() => handleDailyQuickSet(sid, '')}
                                    title="Kosongkan sel"
                                  >
                                    &times;
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                /* MODE 2: DASARIAN GRID */
                <div className="dasarian-input-table-wrapper">
                  <table className="dasarian-input-table">
                    <thead>
                      <tr>
                        <th className="sticky-col col-stn-info" style={{ left: 0, zIndex: 12 }}>
                          Stasiun Master ({filteredStations.length})
                        </th>
                        {dasarianDates.map((dt) => {
                          const dayNum = parseInt(dt.split('-')[2], 10);
                          return (
                            <th key={dt} className="dasarian-day-th">
                              <span className="th-day-num">{dayNum}</span>
                              <span className="th-day-mon">
                                {dasarianMonth === '9' ? 'Sep' : dasarianMonth}
                              </span>
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredStations.map((stn) => {
                        const sid = stn.station_id;
                        return (
                          <tr key={sid}>
                            <td className="sticky-col col-stn-info" style={{ left: 0, zIndex: 10 }}>
                              <div className="dasarian-stn-cell">
                                <div className="flex-align gap-1">
                                  <span className="font-bold text-xs">{stn.station_name}</span>

                                </div>
                                <span className="font-mono text-3xs text-muted">
                                  {sid} &bull; {stn.kabupaten || stn.regency}
                                </span>
                              </div>
                            </td>

                            {dasarianDates.map((dt) => {
                              const cellKey = `${sid}_${dt}`;
                              const currentDb = dasarianCurrentValues[sid]?.[dt];
                              const cellVal = dasarianInputs[cellKey] !== undefined ? dasarianInputs[cellKey] : '';
                              const isFilled = cellVal !== '';

                              return (
                                <td key={dt} className={`dasarian-cell-td ${isFilled ? 'cell-user-filled' : ''}`}>
                                  <input
                                    type="text"
                                    className={`input-cell-dasarian ${isFilled ? 'filled' : ''}`}
                                    placeholder={
                                      currentDb
                                        ? currentDb.obs_status === 'TTU'
                                          ? 'TTU'
                                          : `${currentDb.rainfall_mm}`
                                        : '—'
                                    }
                                    value={cellVal}
                                    onChange={(e) => {
                                      const v = e.target.value;
                                      setDasarianInputs((prev) => ({ ...prev, [cellKey]: v }));
                                    }}
                                  />
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Input Footer with Summary & Validate Button */}
              <div className="input-modal-footer">
                <div className="footer-left-info">
                  <span className="text-xs text-muted">
                    Total input aktif:{' '}
                    <strong className="text-forest font-mono">{collectEntries().length}</strong> sel observasi
                  </span>
                </div>

                <div className="flex-align gap-2">
                  <button type="button" className="btn btn-outline" onClick={handleModalClose}>
                    Batal
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleValidatePreview}
                    disabled={
                      previewLoading ||
                      collectEntries().length === 0 ||
                      stationsLoading ||
                      !!stationsError ||
                      stations.length === 0
                    }
                  >
                    {previewLoading ? (
                      <>
                        <div className="spin spinner-xs"></div>
                        <span>Memvalidasi...</span>
                      </>
                    ) : (
                      <>
                        <ArrowRight size={14} />
                        <span>Pratinjau &amp; Validasi Data</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: PREVIEW & DIFFERENCE VERIFICATION */}
          {step === 'PREVIEW' && previewData && (
            <div className="rainfall-preview-flow">
              <div className="preview-summary-cards">
                <div className="preview-kpi-card kpi-new">
                  <span className="pkpi-label">Data Baru (Belum ada di DB)</span>
                  <span className="pkpi-count font-mono">{previewData.total_new}</span>
                  <span className="pkpi-desc">Akan ditambahkan ke MariaDB</span>
                </div>

                <div className="preview-kpi-card kpi-identical">
                  <span className="pkpi-label">Data Identik (Sama persis)</span>
                  <span className="pkpi-count font-mono">{previewData.total_identical}</span>
                  <span className="pkpi-desc">Akan dilewati (tanpa penulisan ulang)</span>
                </div>

                <div className={`preview-kpi-card kpi-diff ${previewData.total_diff > 0 ? 'highlight-alert' : ''}`}>
                  <span className="pkpi-label">Data Berbeda (Koreksi)</span>
                  <span className="pkpi-count font-mono">{previewData.total_diff}</span>
                  <span className="pkpi-desc">
                    {previewData.total_diff > 0 ? 'Memerlukan konfirmasi penimpaan' : 'Tidak ada perbedaan'}
                  </span>
                </div>

                <div className={`preview-kpi-card kpi-invalid ${previewData.total_invalid > 0 ? 'highlight-err' : ''}`}>
                  <span className="pkpi-label">Input Tidak Valid</span>
                  <span className="pkpi-count font-mono">{previewData.total_invalid}</span>
                  <span className="pkpi-desc">
                    {previewData.total_invalid > 0 ? 'Ditolak secara otomatis' : 'Semua format valid'}
                  </span>
                </div>
              </div>

              {/* Overwrite Confirmation if DIFF records exist */}
              {previewData.total_diff > 0 && (
                <div className="preview-diff-alert-box">
                  <div className="diff-alert-header">
                    <AlertTriangle size={18} className="text-amber-700" />
                    <h4 className="font-bold text-sm text-amber-900">
                      Perhatian: Ditemukan {previewData.total_diff} Data Berbeda dengan Database
                    </h4>
                  </div>
                  <p className="text-xs text-amber-900 mt-1">
                    Nilai yang Anda masukkan berbeda dari nilai observasi yang sudah tersimpan di database. Sistem tidak menimpa data lama tanpa konfirmasi eksplisit dari Anda.
                  </p>

                  <div className="diff-table-container mt-2">
                    <table className="diff-preview-table">
                      <thead>
                        <tr>
                          <th>Stasiun</th>
                          <th>Tanggal</th>
                          <th>Nilai Lama di DB</th>
                          <th>Nilai Baru Input</th>
                          <th>Status Lama</th>
                          <th>Status Baru</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.items
                          .filter((it) => it.category === 'DIFF')
                          .map((it, idx) => (
                            <tr key={idx}>
                              <td className="font-semibold text-xs">
                                {it.station_name || it.station_id} ({it.station_id})
                              </td>
                              <td className="font-mono text-xs">{it.date}</td>
                              <td className="font-mono text-xs text-muted">
                                {it.old_value !== null ? `${it.old_value} mm` : '—'}
                              </td>
                              <td className="font-mono text-xs font-bold text-forest">
                                {it.new_value !== null ? `${it.new_value} mm` : '—'}
                              </td>
                              <td className="text-2xs">{it.old_status}</td>
                              <td className="text-2xs font-semibold">{it.new_status}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="diff-confirmation-controls mt-3">
                    <label className="checkbox-confirm-label">
                      <input
                        type="checkbox"
                        checked={confirmOverwrite}
                        onChange={(e) => setConfirmOverwrite(e.target.checked)}
                      />
                      <span>
                        <strong>Saya mengonfirmasi untuk mengganti/mengoreksi {previewData.total_diff} data lama dengan data baru yang berbeda.</strong>
                      </span>
                    </label>

                    <div className="diff-reason-field mt-2">
                      <label className="text-xs font-semibold text-secondary">Alasan Koreksi (Audit Log):</label>
                      <input
                        type="text"
                        className="input-text-reason"
                        value={correctionReason}
                        onChange={(e) => setCorrectionReason(e.target.value)}
                        placeholder="Misal: Koreksi nilai observasi manual operasional"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Invalid items warning */}
              {previewData.total_invalid > 0 && (
                <div className="preview-invalid-alert-box mt-2">
                  <div className="flex-align gap-2">
                    <AlertCircle size={16} className="text-red" />
                    <span className="font-bold text-xs text-red">
                      {previewData.total_invalid} data tidak valid terdeteksi dan akan diabaikan/ditolak:
                    </span>
                  </div>
                  <ul className="invalid-list-bullet">
                    {previewData.items
                      .filter((it) => it.category === 'INVALID')
                      .map((it, idx) => (
                        <li key={idx} className="text-2xs text-red">
                          Stasiun {it.station_id} ({it.date}): {it.reason}
                        </li>
                      ))}
                  </ul>
                </div>
              )}

              {/* Preview Footer */}
              <div className="input-modal-footer">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setStep('INPUT')}
                  disabled={commitLoading}
                >
                  &larr; Kembali ke Formulir
                </button>

                <div className="flex-align gap-2">
                  <button
                    type="button"
                    className="btn btn-success"
                    onClick={handleCommit}
                    disabled={commitLoading || (previewData.total_diff > 0 && !confirmOverwrite) || previewData.total_valid === 0}
                  >
                    {commitLoading ? (
                      <>
                        <div className="spin spinner-xs"></div>
                        <span>Menyimpan ke MariaDB...</span>
                      </>
                    ) : (
                      <>
                        <Save size={14} />
                        <span>Simpan {previewData.total_valid} Data ke MariaDB</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: RESULT & AUDIT CONFIRMATION */}
          {step === 'RESULT' && commitResult && (
            <div className="rainfall-result-flow">
              <div className="result-success-box">
                <CheckCircle2 size={40} className="text-emerald-600 mb-2" />
                <h3 className="font-bold text-base text-emerald-900">Penyimpanan Berhasil!</h3>
                <p className="text-xs text-emerald-800 mt-1 max-w-md text-center">
                  {commitResult.message}
                </p>

                <div className="result-metrics-grid mt-3">
                  <div className="result-metric-item">
                    <span className="text-3xs text-muted uppercase font-bold">Total Tersimpan</span>
                    <span className="text-base font-extrabold font-mono text-emerald-800">
                      {commitResult.total_saved}
                    </span>
                  </div>
                  <div className="result-metric-item">
                    <span className="text-3xs text-muted uppercase font-bold">Data Baru</span>
                    <span className="text-base font-extrabold font-mono text-blue-800">
                      {commitResult.new_count}
                    </span>
                  </div>
                  <div className="result-metric-item">
                    <span className="text-3xs text-muted uppercase font-bold">Data Dikoreksi</span>
                    <span className="text-base font-extrabold font-mono text-amber-800">
                      {commitResult.corrected_count}
                    </span>
                  </div>
                  <div className="result-metric-item">
                    <span className="text-3xs text-muted uppercase font-bold">Identik Dilewati</span>
                    <span className="text-base font-extrabold font-mono text-slate-600">
                      {commitResult.skipped_identical_count}
                    </span>
                  </div>
                </div>

                <div className="result-batch-info mt-3 font-mono text-3xs text-muted">
                  Batch ID: {commitResult.batch_id} &bull; Tercatat di staging_rainfall_import &amp; cews_rainfall_correction_log
                </div>

                <button
                  type="button"
                  className="btn btn-primary mt-4"
                  onClick={handleModalClose}
                >
                  <Check size={14} className="inline-icon" />
                  Selesai &amp; Perbarui Tampilan Tabel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
