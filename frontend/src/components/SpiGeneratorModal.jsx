import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  X,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Cpu,
  Calendar,
  Layers,
  Search,
  Filter,
  CheckSquare,
  Square,
  ArrowRight,
  Database,
  BarChart2
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

export default function SpiGeneratorModal({
  isOpen,
  onClose,
  onGenerationSuccess
}) {
  // Wizard Step: 1 = Configure & Preview, 2 = Generating, 3 = Completed, 4 = Error
  const [step, setStep] = useState(1);

  // Configuration State
  const [resolution, setResolution] = useState('DASARIAN'); // 'HARIAN' | 'DASARIAN' | 'BULANAN'
  const [timescale, setTimescale] = useState(30);           // 30 | 90
  const [outputStartDate, setOutputStartDate] = useState('');
  const [outputEndDate, setOutputEndDate] = useState('');
  const [stationSearchQuery, setStationSearchQuery] = useState('');
  const [selectedStationIds, setSelectedStationIds] = useState([]);
  const [workerCount, setWorkerCount] = useState(4);
  const [operatorNotes, setOperatorNotes] = useState('Kalkulasi SPI operasional BMKG RHF');

  // Backend Options & Preview State
  const [optionsData, setOptionsData] = useState(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsError, setOptionsError] = useState(null);
  const [previewSummary, setPreviewSummary] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState(null);

  // Execution & Staging Session State
  const [executing, setExecuting] = useState(false);
  const [execResult, setExecResult] = useState(null);
  const [execError, setExecError] = useState(null);
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitResult, setCommitResult] = useState(null);

  // 1. Fetch initial options when modal opens
  const fetchOptions = useCallback(async () => {
    setOptionsLoading(true);
    setOptionsError(null);
    try {
      const res = await authFetch(API_ENDPOINTS.SPI_GENERATOR_OPTIONS);
      if (res.ok) {
        const data = await res.json();
        setOptionsData(data);
        // Default select all 52 eligible manual stations
        if (data.stations) {
          const defaultSids = data.stations
            .filter((s) => s.eligible_for_spi)
            .map((s) => s.station_id);
          setSelectedStationIds(defaultSids);
        }
      } else {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Gagal memuat daftar master pos pengamatan.`);
      }
    } catch (err) {
      console.error('Failed to load SPI generator options:', err);
      setOptionsError(err.message || 'Gagal terhubung ke API opsi Generator SPI');
    } finally {
      setOptionsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setExecResult(null);
      setExecError(null);
      setCommitResult(null);
      setPreviewSummary(null);
      setOutputStartDate('');
      setOutputEndDate('');
      fetchOptions();
    }
  }, [isOpen, fetchOptions]);

  // Handle Resolution Change
  const handleResolutionChange = (res) => {
    setResolution(res);
    setPreviewSummary(null);
  };

  // 2. Fetch Preview Feasibility
  const handleFetchPreview = async () => {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const payload = {
        resolution,
        timescale: Number(timescale),
        selected_stations: selectedStationIds.length > 0 ? selectedStationIds : null,
        output_start_date: outputStartDate || null,
        output_end_date: outputEndDate || null
      };
      const res = await authFetch(API_ENDPOINTS.SPI_GENERATOR_PREVIEW, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Gagal memuat pratinjau kalkulasi`);
      }
      const data = await res.json();
      setPreviewSummary(data);
    } catch (err) {
      setPreviewError(err.message);
      setPreviewSummary(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  // 3. Execute Parallel Calculation
  const handleExecuteCalculation = async () => {
    setExecuting(true);
    setExecError(null);
    setStep(2);
    try {
      const payload = {
        resolution,
        timescale: Number(timescale),
        selected_stations: selectedStationIds.length > 0 ? selectedStationIds : null,
        output_start_date: outputStartDate || null,
        output_end_date: outputEndDate || null,
        n_workers: Number(workerCount) || 4
      };
      const res = await authFetch(API_ENDPOINTS.SPI_GENERATOR_EXECUTE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Kalkulasi SPI gagal.`);
      }
      const data = await res.json();
      setExecResult(data);
      setStep(3);
    } catch (err) {
      setExecError(err.message);
      setStep(4);
    } finally {
      setExecuting(false);
    }
  };

  // 4. Commit Staged SPI into Canonical Parquet
  const handleCommitParquet = async () => {
    if (!execResult?.session_token) return;
    setCommitLoading(true);
    try {
      const payload = {
        session_token: execResult.session_token,
        operator_notes: operatorNotes || 'Pembaruan SPI otomatis'
      };
      const res = await authFetch(API_ENDPOINTS.SPI_GENERATOR_COMMIT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Gagal commit ke penyimpanan kanonikal`);
      }
      const data = await res.json();
      setCommitResult(data);
      if (onGenerationSuccess) {
        onGenerationSuccess(data);
      }
    } catch (err) {
      alert(`Commit Gagal: ${err.message}`);
    } finally {
      setCommitLoading(false);
    }
  };

  // Filter stations list for station selection toolbar
  // Ensure only the 52 manual stations are eligible and displayed for selection
  const availableStations = useMemo(() => {
    return (optionsData?.stations || []).filter((s) => s.eligible_for_spi && !s.is_arg);
  }, [optionsData]);

  const filteredStations = useMemo(() => {
    if (!stationSearchQuery.trim()) return availableStations;
    const q = stationSearchQuery.toLowerCase().trim();
    return availableStations.filter((s) => {
      const name = (s.station_name || '').toLowerCase();
      const id = (s.station_id || '').toLowerCase();
      const kab = (s.kabupaten || '').toLowerCase();
      return name.includes(q) || id.includes(q) || kab.includes(q);
    });
  }, [availableStations, stationSearchQuery]);

  const toggleStationSelection = (sid) => {
    setSelectedStationIds((prev) =>
      prev.includes(sid) ? prev.filter((id) => id !== sid) : [...prev, sid]
    );
    setPreviewSummary(null);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in duration-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/80">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-indigo-100 text-indigo-700">
              <Cpu size={22} />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-800">
                Generator Nilai SPI (Standardized Precipitation Index)
              </h3>
              <p className="text-xs text-slate-500">
                Perhitungan SPI berbasis distribusi terbaik (BestDist) per pos pengamatan langsung dari data curah hujan MariaDB
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition"
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          
          {/* STEP 1: Configuration & Feasibility Check */}
          {step === 1 && (
            <div className="space-y-5">
              
              {/* Rain Data Baseline Status */}
              {optionsData?.rainfall_data_range && (
                <div className="p-3.5 bg-emerald-50/80 border border-emerald-200 rounded-lg flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2 text-emerald-800">
                    <Database size={16} className="text-emerald-600 shrink-0" />
                    <span>
                      Basis Data Curah Hujan Tersedia: <strong>{optionsData.rainfall_data_range.start_date}</strong> s.d. <strong>{optionsData.rainfall_data_range.end_date}</strong> ({optionsData.rainfall_data_range.stations_reporting} Stasiun)
                    </span>
                  </div>
                  <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded border border-emerald-300">
                    Siap Dihitung
                  </span>
                </div>
              )}

              {/* Form Grid: Resolution, Timescale, Dates */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                
                {/* 1. Resolusi */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-700">1. Resolusi Waktu</label>
                  <select
                    className="w-full text-xs p-2.5 border border-slate-300 rounded-lg bg-white text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    value={resolution}
                    onChange={(e) => handleResolutionChange(e.target.value)}
                  >
                    <option value="DASARIAN">Dasarian (Dekad / 10-harian)</option>
                    <option value="HARIAN">Harian (Daily / Kalender)</option>
                    <option value="BULANAN">Bulanan (Monthly / Kalender)</option>
                  </select>
                  <p className="text-[11px] text-slate-500">
                    {resolution === 'DASARIAN' && 'Digunakan langsung oleh Decision Engine PDKM'}
                    {resolution === 'HARIAN' && 'Resolusi harian untuk analisis deret dinamis'}
                    {resolution === 'BULANAN' && 'Resolusi bulanan untuk ikhtisar klimatologis'}
                  </p>
                </div>

                {/* 2. Timescale */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-700">2. Skala Akumulasi (Timescale)</label>
                  <select
                    className="w-full text-xs p-2.5 border border-slate-300 rounded-lg bg-white text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    value={timescale}
                    onChange={(e) => { setTimescale(Number(e.target.value)); setPreviewSummary(null); }}
                  >
                    <option value={30}>
                      {resolution === 'DASARIAN' ? 'SPI 3 Dasarian (30D)' : resolution === 'BULANAN' ? 'SPI 1 Bulan (30D)' : 'SPI 30 Hari (30D)'}
                    </option>
                    <option value={90}>
                      {resolution === 'DASARIAN' ? 'SPI 9 Dasarian (90D)' : resolution === 'BULANAN' ? 'SPI 3 Bulan (90D)' : 'SPI 90 Hari (90D)'}
                    </option>
                  </select>
                  <p className="text-[11px] text-slate-500">
                    Otomatis mencocokkan distribusi <code>BestDist_Consensus</code> pada skala {timescale}
                  </p>
                </div>

                {/* 3. Output Date Range Filter */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-700">3. Filter Periode Keluaran (Opsional)</label>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="date"
                      className="text-xs p-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500"
                      value={outputStartDate}
                      onChange={(e) => { setOutputStartDate(e.target.value); setPreviewSummary(null); }}
                      title="Mulai tanggal keluaran"
                    />
                    <input
                      type="date"
                      className="text-xs p-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500"
                      value={outputEndDate}
                      onChange={(e) => { setOutputEndDate(e.target.value); setPreviewSummary(null); }}
                      title="Sampai tanggal keluaran"
                    />
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Biarkan kosong untuk menghitung seluruh rentang deret waktu
                  </p>
                </div>
              </div>

              {/* Station Selection Box */}
              <div className="space-y-2.5 border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center space-x-2">
                    <label className="text-xs font-bold text-slate-800">
                      Pilihan Pos Hujan Target ({selectedStationIds.length} dipilih)
                    </label>
                    <span className="text-[11px] text-slate-500">
                      
                    </span>
                  </div>
                  <div className="flex items-center space-x-2 text-xs">
                    <button
                      type="button"
                      className="text-indigo-600 hover:text-indigo-800 font-semibold"
                      onClick={() => {
                        const allEligible = availableStations.map((s) => s.station_id);
                        setSelectedStationIds(allEligible);
                        setPreviewSummary(null);
                      }}
                    >
                      Pilih Semua Stasiun ({availableStations.length})
                    </button>
                    <span className="text-slate-300">|</span>
                    <button
                      type="button"
                      className="text-slate-500 hover:text-slate-700 font-semibold"
                      onClick={() => {
                        setSelectedStationIds([]);
                        setPreviewSummary(null);
                      }}
                    >
                      Kosongkan
                    </button>
                  </div>
                </div>

                {/* Station Search Input */}
                <div className="relative">
                  <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    className="w-full text-xs pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="Saring nama pos, ID pos, atau kabupaten..."
                    value={stationSearchQuery}
                    onChange={(e) => setStationSearchQuery(e.target.value)}
                  />
                </div>

                {/* Loading / Error / Empty / Scrollable Station List (Height ~220px) */}
                {optionsLoading ? (
                  <div className="h-[220px] flex items-center justify-center text-xs text-slate-500 bg-white border border-slate-200 rounded-md">
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                      <span>Memuat master 57 stasiun...</span>
                    </div>
                  </div>
                ) : optionsError ? (
                  <div className="h-[220px] flex flex-col items-center justify-center p-4 text-xs text-rose-600 bg-rose-50/50 border border-rose-200 rounded-md space-y-2">
                    <AlertCircle size={20} className="text-rose-500" />
                    <span>{optionsError}</span>
                    <button
                      type="button"
                      onClick={fetchOptions}
                      className="px-3 py-1 bg-white border border-rose-300 rounded text-rose-700 hover:bg-rose-100 font-semibold transition"
                    >
                      Muat Ulang Stasiun
                    </button>
                  </div>
                ) : filteredStations.length === 0 ? (
                  <div className="h-[220px] flex flex-col items-center justify-center text-xs text-slate-400 bg-white border border-slate-200 rounded-md">
                    <span>Tidak ada pos hujan yang sesuai dengan pencarian "{stationSearchQuery}"</span>
                  </div>
                ) : (
                  <div className="h-[220px] overflow-y-auto divide-y divide-slate-100 bg-white border border-slate-200 rounded-md shadow-inner pr-1">
                    {filteredStations.map((s) => {
                      const isSelected = selectedStationIds.includes(s.station_id);
                      return (
                        <div
                          key={s.station_id}
                          onClick={() => toggleStationSelection(s.station_id)}
                          className={`flex items-center justify-between px-3 py-2 text-xs cursor-pointer transition select-none ${
                            isSelected
                              ? 'bg-indigo-50/80 hover:bg-indigo-100/70 text-indigo-950 font-medium'
                              : 'hover:bg-slate-50 text-slate-700'
                          }`}
                        >
                          <div className="flex items-center space-x-2.5 min-w-0">
                            <div className="shrink-0">
                              {isSelected ? (
                                <CheckSquare size={16} className="text-indigo-600" />
                              ) : (
                                <Square size={16} className="text-slate-400" />
                              )}
                            </div>
                            <div className="flex items-center space-x-2 truncate">
                              <span className="font-semibold text-slate-800">{s.station_name}</span>
                              <span className="text-slate-300 font-mono">|</span>
                              <span className="font-mono text-slate-500 text-[11px]">{s.station_id}</span>
                              <span className="text-slate-300 font-mono">|</span>
                              <span className="text-slate-500 text-[11px]">{s.kabupaten}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Feasibility Check Trigger */}
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  className="inline-flex items-center space-x-1.5 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-300 transition"
                  onClick={handleFetchPreview}
                  disabled={previewLoading || selectedStationIds.length === 0}
                >
                  <BarChart2 size={14} />
                  <span>{previewLoading ? 'Memeriksa Distribusi...' : '1. Pratinjau Kelayakan Perhitungan'}</span>
                </button>

                {previewSummary && (
                  <button
                    type="button"
                    className="inline-flex items-center space-x-2 px-5 py-2 bg-indigo-700 hover:bg-indigo-800 text-white text-xs font-bold rounded-lg shadow transition"
                    onClick={handleExecuteCalculation}
                  >
                    <Play size={14} />
                    <span>2. Jalankan Perhitungan SPI ({previewSummary.summary.eligible_stations_count} Pos)</span>
                  </button>
                )}
              </div>

              {/* Preview Summary Box */}
              {previewSummary && (
                <div className="p-4 bg-slate-50 border border-slate-300 rounded-lg space-y-3 animate-in fade-in">
                  <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                    <span className="text-xs font-bold text-slate-800">
                      Ringkasan Kelayakan: {previewSummary.resolution} {previewSummary.timescale}D (fit_freq: <code>{previewSummary.fit_freq}</code>)
                    </span>
                    <span className="text-xs text-indigo-700 font-semibold">
                      Target: {previewSummary.target_parquet_path}
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="p-2 bg-white rounded border border-slate-200">
                      <span className="text-slate-500 block text-[11px]">Diminta</span>
                      <strong className="text-sm text-slate-800">{previewSummary.summary.total_requested_stations} Pos</strong>
                    </div>
                    <div className="p-2 bg-emerald-50 rounded border border-emerald-200">
                      <span className="text-emerald-700 block text-[11px]">Distribusi Valid</span>
                      <strong className="text-sm text-emerald-800">{previewSummary.summary.eligible_stations_count} Pos</strong>
                    </div>
                    <div className="p-2 bg-amber-50 rounded border border-amber-200">
                      <span className="text-amber-700 block text-[11px]">Dikecualikan / Tidak Ada</span>
                      <strong className="text-sm text-amber-800">{previewSummary.summary.ineligible_stations_count} Pos</strong>
                    </div>
                  </div>

                  {/* Distribution sample chips */}
                  <div className="text-xs">
                    <span className="font-semibold text-slate-700 block mb-1">Sampel Distribusi Terbaik yang Akan Dipakai:</span>
                    <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                      {previewSummary.eligible_stations.slice(0, 15).map((e) => (
                        <span key={e.station_id} className="text-[10px] bg-white border border-slate-200 px-1.5 py-0.5 rounded text-slate-700">
                          {e.station_name}: <strong className="text-indigo-600">{e.dist_name}</strong>
                        </span>
                      ))}
                      {previewSummary.eligible_stations.length > 15 && (
                        <span className="text-[10px] text-slate-500 self-center">
                          +{previewSummary.eligible_stations.length - 15} pos lainnya...
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {previewError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-center space-x-2">
                  <AlertCircle size={16} />
                  <span>{previewError}</span>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: Processing in Background */}
          {step === 2 && (
            <div className="py-12 flex flex-col items-center justify-center space-y-4 text-center">
              <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <div>
                <h4 className="text-sm font-bold text-slate-800">Menjalankan Perhitungan SPI Multiprocessing...</h4>
                <p className="text-xs text-slate-500 mt-1">
                  Menerapkan fitting distribusi terbaik (<code>BestDist_Consensus</code>) secara paralel untuk deret waktu pos hujan
                </p>
              </div>
              <div className="text-[11px] text-slate-400 font-mono">
                Menggunakan engine Joblib (backend: loky, {workerCount} workers)
              </div>
            </div>
          )}

          {/* STEP 3: Results Preview & Confirmation to Commit */}
          {step === 3 && execResult && (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-lg flex items-center space-x-3">
                <CheckCircle2 size={24} className="text-emerald-600 shrink-0" />
                <div>
                  <h4 className="text-xs font-bold text-emerald-900">
                    Kalkulasi SPI Selesai & Berada di Memori Staging
                  </h4>
                  <p className="text-xs text-emerald-700">
                    {execResult.summary.success_count} pos berhasil dihitung ({execResult.summary.computed_rows} baris deret waktu). File kanonikal belum diubah.
                  </p>
                </div>
              </div>

              {/* Sample output preview */}
              {execResult.sample_preview && (
                <div className="border border-slate-200 rounded-lg overflow-hidden text-xs">
                  <div className="bg-slate-100 px-3 py-2 font-bold text-slate-700 border-b border-slate-200">
                    Pratinjau Sampel Nilai SPI Terbaru (5 Tanggal Terakhir):
                  </div>
                  <div className="p-3 bg-white font-mono text-[11px] space-y-1">
                    {execResult.sample_preview.dates.map((d, i) => (
                      <div key={d} className="flex space-x-4">
                        <span className="text-slate-500 w-24">{d}:</span>
                        <span className="text-slate-800 font-semibold">
                          {JSON.stringify(execResult.sample_preview.values[i])}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Commit Notes */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700">Catatan Pembaruan Operator:</label>
                <input
                  type="text"
                  className="w-full text-xs p-2.5 border border-slate-300 rounded-lg"
                  value={operatorNotes}
                  onChange={(e) => setOperatorNotes(e.target.value)}
                />
              </div>

              {/* Commit Actions */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-200">
                <button
                  type="button"
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg"
                  onClick={() => setStep(1)}
                  disabled={commitLoading}
                >
                  &larr; Ubah Konfigurasi
                </button>

                <button
                  type="button"
                  className="inline-flex items-center space-x-2 px-6 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold rounded-lg shadow transition"
                  onClick={handleCommitParquet}
                  disabled={commitLoading}
                >
                  <Database size={15} />
                  <span>{commitLoading ? 'Menyimpan ke Parquet...' : 'Simpan & Terapkan ke Sistem DSS-PIK'}</span>
                </button>
              </div>

              {commitResult && (
                <div className="p-3 bg-sky-50 border border-sky-300 rounded-lg text-xs text-sky-800 flex items-center justify-between">
                  <span>{commitResult.message}</span>
                  <button
                    type="button"
                    className="font-bold underline ml-2"
                    onClick={onClose}
                  >
                    Tutup Modal
                  </button>
                </div>
              )}
            </div>
          )}

          {/* STEP 4: Error State */}
          {step === 4 && (
            <div className="py-8 text-center space-y-4">
              <div className="p-3 bg-rose-100 text-rose-700 rounded-full w-12 h-12 flex items-center justify-center mx-auto">
                <AlertTriangle size={24} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-rose-900">Kalkulasi SPI Gagal</h4>
                <p className="text-xs text-rose-600 mt-1 max-w-md mx-auto">{execError}</p>
              </div>
              <button
                type="button"
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 text-xs font-semibold rounded-lg"
                onClick={() => setStep(1)}
              >
                Kembali ke Pengaturan
              </button>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <span>Engine Perhitungan: <code>si.spi</code> &bull; Probabilitas Nol: <code>stagge</code> &bull; Fitting: <code>standard</code></span>
          <button
            type="button"
            className="text-slate-600 hover:text-slate-800 font-medium"
            onClick={onClose}
          >
            Tutup
          </button>
        </div>

      </div>
    </div>
  );
}

