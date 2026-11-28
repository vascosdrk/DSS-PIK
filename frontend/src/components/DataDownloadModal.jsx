import React, { useState, useEffect, useMemo } from 'react';
import {
  X,
  Download,
  FileSpreadsheet,
  FileText,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Activity,
  Droplets,
  CloudRain,
  Loader2,
  Database,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

function normalizeInitialType(raw) {
  if (!raw) return 'RAINFALL';
  const u = String(raw).toUpperCase();
  if (u === 'PROBABILITY' || u === 'ECMWF' || u === 'DETERMINISTIC') return 'ECMWF';
  if (u === 'SPI') return 'SPI';
  return 'RAINFALL';
}

function defaultWindowStart(minDate, maxDate, daysBack = 30) {
  if (!maxDate) return minDate || '';
  const maxDt = new Date(`${maxDate}T00:00:00`);
  if (Number.isNaN(maxDt.getTime())) return minDate || maxDate;
  const cand = new Date(maxDt);
  cand.setDate(cand.getDate() - daysBack);
  const candStr = cand.toISOString().slice(0, 10);
  if (minDate && candStr < minDate) return minDate;
  return candStr;
}

/**
 * DataDownloadModal — Pusat Unduh Data DSS-PIK
 * Seluruh opsi rentang tanggal, periode, dan vintage mengikuti isi database aktual
 * melalui GET /api/v1/export/availability (tanpa tanggal atau periode statis).
 */
export default function DataDownloadModal({
  isOpen,
  onClose,
  initialDataType = 'RAINFALL',
  initialParams = {},
}) {
  // 3 Primary Categories: 'RAINFALL' | 'SPI' | 'ECMWF'
  const [dataType, setDataType] = useState(normalizeInitialType(initialDataType));
  const [fileFormat, setFileFormat] = useState('xlsx'); // 'xlsx' | 'csv'

  // Live metadata from backend
  const [availability, setAvailability] = useState(null);
  const [loadingMeta, setLoadingMeta] = useState(false);
  const [metaError, setMetaError] = useState('');

  // Stations master list
  const [stationsMaster, setStationsMaster] = useState([]);
  const [stationSelectionMode, setStationSelectionMode] = useState('ALL'); // 'ALL' | 'SINGLE' | 'MULTI'
  const [selectedStationIds, setSelectedStationIds] = useState([]);

  // Rainfall / SPI date range (strictly hydrated from actual DB availability)
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // SPI options
  const [spiPeriodType, setSpiPeriodType] = useState('DASARIAN'); // 'DASARIAN' | 'DAILY'
  const [spiTimescale, setSpiTimescale] = useState('30D'); // '30D' | '90D'

  // ECMWF options
  const [ecmwfResolution, setEcmwfResolution] = useState('DASARIAN'); // 'DASARIAN' | 'BULANAN'
  const [ecmwfDataType, setEcmwfDataType] = useState('PROBABILITAS'); // 'PROBABILITAS' | 'DETERMINISTIK'
  const [selectedPeriodId, setSelectedPeriodId] = useState('');
  const [selectedIssueDate, setSelectedIssueDate] = useState('');

  // Download feedback state
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  // Sync initial props on open
  useEffect(() => {
    if (!isOpen) return;
    setDataType(normalizeInitialType(initialDataType));
    if (initialParams?.periodType) setSpiPeriodType(initialParams.periodType);
    if (initialParams?.timescale) setSpiTimescale(initialParams.timescale);
    if (initialParams?.ecmwfResolution) setEcmwfResolution(initialParams.ecmwfResolution);
    if (initialParams?.ecmwfDataType) setEcmwfDataType(initialParams.ecmwfDataType);
    setDownloadError('');
    setDownloadSuccess(false);
  }, [isOpen, initialDataType, initialParams]);

  // Escape key & scroll lock
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  // Fetch live export availability + master stations on open
  useEffect(() => {
    if (!isOpen) return;
    setLoadingMeta(true);
    setMetaError('');
    Promise.all([
      authFetch(API_ENDPOINTS.EXPORT_AVAILABILITY).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      }),
      authFetch(API_ENDPOINTS.STATIONS_MASTER).then((r) => (r.ok ? r.json() : { stations: [] })),
    ])
      .then(([availData, stnData]) => {
        setAvailability(availData);
        if (stnData && Array.isArray(stnData.stations)) {
          setStationsMaster(stnData.stations);
        }
      })
      .catch((err) => {
        console.error('Failed to load export availability:', err);
        setMetaError('Gagal memuat ketersediaan data aktual dari server.');
      })
      .finally(() => setLoadingMeta(false));
  }, [isOpen]);

  // Active availability slices
  const rainfallMeta = availability?.rainfall || null;
  const spiMeta = availability?.spi?.[`${spiPeriodType}_${spiTimescale}`] || null;
  const ecmwfBranchKey = ecmwfDataType === 'DETERMINISTIK' ? 'deterministic' : 'probability';
  const ecmwfMeta = availability?.ecmwf?.[ecmwfBranchKey]?.[ecmwfResolution] || null;

  // Hydrate Rainfall / SPI date range strictly from actual DB bounds
  useEffect(() => {
    if (!availability) return;
    if (dataType === 'RAINFALL') {
      if (rainfallMeta?.available && rainfallMeta.max_date) {
        setEndDate(rainfallMeta.max_date);
        setStartDate(defaultWindowStart(rainfallMeta.min_date, rainfallMeta.max_date, 30));
      } else {
        setStartDate('');
        setEndDate('');
      }
    } else if (dataType === 'SPI') {
      if (spiMeta?.available && spiMeta.max_date) {
        setEndDate(spiMeta.max_date);
        setStartDate(defaultWindowStart(spiMeta.min_date, spiMeta.max_date, 180));
      } else {
        setStartDate('');
        setEndDate('');
      }
    }
  }, [availability, dataType, spiPeriodType, spiTimescale, rainfallMeta, spiMeta]);

  // Hydrate ECMWF target period & active vintage strictly from actual DB records
  const availableEcmwfPeriods = useMemo(() => ecmwfMeta?.periods || [], [ecmwfMeta]);

  useEffect(() => {
    if (dataType !== 'ECMWF') return;
    if (availableEcmwfPeriods.length > 0) {
      const matched = availableEcmwfPeriods.find((p) => p.period_id === selectedPeriodId);
      const targetPeriod = matched || availableEcmwfPeriods[0];
      setSelectedPeriodId(targetPeriod.period_id);
      const vList = targetPeriod.available_vintages || [];
      setSelectedIssueDate(vList[0] || targetPeriod.latest_vintage || targetPeriod.latest_issue_date || '');
    } else {
      setSelectedPeriodId('');
      setSelectedIssueDate('');
    }
  }, [dataType, ecmwfResolution, ecmwfDataType, availableEcmwfPeriods]);

  const activeEcmwfPeriodObj = useMemo(
    () => availableEcmwfPeriods.find((p) => p.period_id === selectedPeriodId) || null,
    [availableEcmwfPeriods, selectedPeriodId]
  );

  const availableVintagesForPeriod = useMemo(() => {
    if (!activeEcmwfPeriodObj) return [];
    const list = activeEcmwfPeriodObj.available_vintages || [];
    if (list.length > 0) return list;
    const fallback = activeEcmwfPeriodObj.latest_vintage || activeEcmwfPeriodObj.latest_issue_date;
    return fallback ? [fallback] : [];
  }, [activeEcmwfPeriodObj]);

  // Keep selectedIssueDate synchronized when target period changes
  const handleSelectEcmwfPeriod = (pid) => {
    setSelectedPeriodId(pid);
    const obj = availableEcmwfPeriods.find((p) => p.period_id === pid);
    const vList = obj?.available_vintages || [];
    setSelectedIssueDate(vList[0] || obj?.latest_vintage || obj?.latest_issue_date || '');
  };

  // Determine whether active dataset is actually available for export
  const isActiveDatasetAvailable = useMemo(() => {
    if (!availability) return false;
    if (dataType === 'RAINFALL') return Boolean(rainfallMeta?.available);
    if (dataType === 'SPI') return Boolean(spiMeta?.available);
    if (dataType === 'ECMWF') {
      return Boolean(ecmwfMeta?.available && selectedPeriodId && selectedIssueDate);
    }
    return false;
  }, [availability, dataType, rainfallMeta, spiMeta, ecmwfMeta, selectedPeriodId, selectedIssueDate]);

  const handleStationToggle = (stnId) => {
    setSelectedStationIds((prev) =>
      prev.includes(stnId) ? prev.filter((id) => id !== stnId) : [...prev, stnId]
    );
  };

  const handleExecuteDownload = async (e) => {
    e.preventDefault();
    if (!isActiveDatasetAvailable) return;
    setDownloading(true);
    setDownloadError('');
    setDownloadSuccess(false);

    try {
      let downloadUrl = '';
      let filename = `DSS_PIK_${dataType}.${fileFormat}`;

      let stnParam = '';
      if (stationSelectionMode === 'SINGLE' && selectedStationIds.length > 0) {
        stnParam = selectedStationIds[0];
      } else if (stationSelectionMode === 'MULTI' && selectedStationIds.length > 0) {
        stnParam = selectedStationIds.join(',');
      }

      if (dataType === 'RAINFALL') {
        const params = { format: fileFormat, start_date: startDate, end_date: endDate };
        if (stnParam) params.station_ids = stnParam;
        downloadUrl = API_ENDPOINTS.RAINFALL_DOWNLOAD(params);
        filename = `Curah_Hujan_${startDate}_sd_${endDate}.${fileFormat}`;
      } else if (dataType === 'SPI') {
        const params = {
          period_type: spiPeriodType,
          timescale: spiTimescale,
          format: fileFormat,
          start_date: startDate,
          end_date: endDate,
        };
        if (stnParam) params.station_ids = stnParam;
        downloadUrl = API_ENDPOINTS.SPI_DOWNLOAD(params);
        filename = `SPI_${spiPeriodType}_${spiTimescale}_${startDate}_sd_${endDate}.${fileFormat}`;
      } else if (dataType === 'ECMWF' && ecmwfDataType === 'PROBABILITAS') {
        const params = {
          period_id: selectedPeriodId,
          issue_date: selectedIssueDate,
          format: fileFormat,
        };
        if (stnParam) params.station_ids = stnParam;
        downloadUrl = API_ENDPOINTS.PROBABILITY_DOWNLOAD(params);
        filename = `Probabilitas_ECMWF_${selectedPeriodId}_ver_${selectedIssueDate}.${fileFormat}`;
      } else if (dataType === 'ECMWF' && ecmwfDataType === 'DETERMINISTIK') {
        const params = {
          period_id: selectedPeriodId,
          resolution: ecmwfResolution,
          issue_date: selectedIssueDate,
          format: fileFormat,
        };
        if (stationSelectionMode === 'SINGLE' && selectedStationIds.length > 0) {
          params.station_id = selectedStationIds[0];
        } else if (stationSelectionMode === 'MULTI' && selectedStationIds.length > 0) {
          params.station_ids = selectedStationIds.join(',');
        }
        downloadUrl = API_ENDPOINTS.DETERMINISTIC_DOWNLOAD(params);
        filename = `Deterministik_ECMWF_${ecmwfResolution.toLowerCase()}_${selectedPeriodId}_ver_${selectedIssueDate}.${fileFormat}`;
      }

      const res = await authFetch(downloadUrl);
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}: Gagal mengekspor berkas.`);
      }

      const disposition = res.headers.get('content-disposition');
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename="?([^";]+)"?/);
        if (match && match[1]) filename = match[1];
      }

      const blob = await res.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(objectUrl);

      setDownloadSuccess(true);
      setTimeout(() => setDownloadSuccess(false), 3000);
    } catch (err) {
      console.error('Export failed:', err);
      setDownloadError(err.message || 'Gagal mengunduh berkas data.');
    } finally {
      setDownloading(false);
    }
  };

  if (!isOpen) return null;

  const canSubmit =
    !loadingMeta &&
    !downloading &&
    isActiveDatasetAvailable &&
    (stationSelectionMode === 'ALL' || selectedStationIds.length > 0) &&
    (dataType === 'ECMWF' || (Boolean(startDate) && Boolean(endDate) && startDate <= endDate));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-3 sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[92vh] flex flex-col overflow-hidden border border-slate-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header — selaras dengan RainfallInputModal */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-800 flex items-center justify-center">
              <Download size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                PUSAT UNDUH DATA DSS-PIK
              </h2>
              <p className="text-[11px] text-slate-500">
                Ekspor resmi berbasis ketersediaan data aktual (Curah Hujan, Indeks SPI, Prakiraan ECMWF)
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition"
            aria-label="Tutup"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleExecuteDownload} className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* 1. Kategori Dataset */}
          <div className="space-y-2">
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
              1. Kategori Dataset
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {[
                {
                  id: 'RAINFALL',
                  title: 'Curah Hujan (CH)',
                  sub: 'Observasi harian (mm)',
                  icon: Droplets,
                },
                {
                  id: 'SPI',
                  title: 'Indeks SPI',
                  sub: 'Dasarian / Harian (30D & 90D)',
                  icon: Activity,
                },
                {
                  id: 'ECMWF',
                  title: 'Prakiraan ECMWF',
                  sub: 'Probabilitas (%) & Deterministik (mm)',
                  icon: CloudRain,
                },
              ].map((cat) => {
                const Icon = cat.icon;
                const active = dataType === cat.id;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => {
                      setDataType(cat.id);
                      setDownloadError('');
                    }}
                    className={`text-left p-3 rounded-xl border transition-all ${
                      active
                        ? 'border-blue-800 bg-blue-50/60 ring-1 ring-blue-800/30'
                        : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <Icon size={17} className={active ? 'text-blue-800' : 'text-slate-400'} />
                      {active && <CheckCircle2 size={14} className="text-blue-800" />}
                    </div>
                    <div className="mt-1.5 text-xs font-bold text-slate-900">{cat.title}</div>
                    <div className="text-[11px] text-slate-500">{cat.sub}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Live Availability Loading / Error */}
          {loadingMeta && (
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-blue-700" />
              <span>Memeriksa ketersediaan data aktual di basis data...</span>
            </div>
          )}

          {metaError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle size={15} />
              <span>{metaError}</span>
            </div>
          )}

          {/* 2A. FILTER CURAH HUJAN */}
          {!loadingMeta && dataType === 'RAINFALL' && (
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="font-bold text-slate-800 inline-flex items-center gap-1.5">
                  <Database size={13} className="text-blue-700" />
                  Ketersediaan Aktual Curah Hujan
                </span>
                {rainfallMeta?.available ? (
                  <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold">
                    {rainfallMeta.min_date} s.d. {rainfallMeta.max_date} &bull; {rainfallMeta.stations_with_data} pos
                  </span>
                ) : (
                  <span className="text-[11px] px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 font-semibold">
                    Belum ada data tersedia
                  </span>
                )}
              </div>

              {rainfallMeta?.available ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Tanggal Mulai
                    </label>
                    <input
                      type="date"
                      value={startDate}
                      min={rainfallMeta.min_date || undefined}
                      max={rainfallMeta.max_date || undefined}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white font-mono text-xs"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Tanggal Selesai
                    </label>
                    <input
                      type="date"
                      value={endDate}
                      min={rainfallMeta.min_date || undefined}
                      max={rainfallMeta.max_date || undefined}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white font-mono text-xs"
                      required
                    />
                  </div>
                </div>
              ) : (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-center gap-2">
                  <AlertTriangle size={14} className="text-amber-600 shrink-0" />
                  <span>Tidak ada data curah hujan aktif yang tersedia untuk diekspor.</span>
                </div>
              )}
            </div>
          )}

          {/* 2B. FILTER SPI */}
          {!loadingMeta && dataType === 'SPI' && (
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Resolusi SPI
                  </span>
                  <div className="grid grid-cols-2 gap-1 p-1 rounded-lg bg-slate-200/70">
                    {[
                      { v: 'DASARIAN', lbl: 'Dasarian' },
                      { v: 'DAILY', lbl: 'Harian' },
                    ].map((opt) => (
                      <button
                        key={opt.v}
                        type="button"
                        onClick={() => setSpiPeriodType(opt.v)}
                        className={`py-1.5 rounded-md text-xs font-semibold transition ${
                          spiPeriodType === opt.v
                            ? 'bg-blue-900 text-white shadow-xs'
                            : 'text-slate-700 hover:bg-white/70'
                        }`}
                      >
                        {opt.lbl}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <span className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Skala Akumulasi
                  </span>
                  <div className="grid grid-cols-2 gap-1 p-1 rounded-lg bg-slate-200/70">
                    {[
                      { v: '30D', lbl: '30 Hari (30D)' },
                      { v: '90D', lbl: '90 Hari (90D)' },
                    ].map((opt) => (
                      <button
                        key={opt.v}
                        type="button"
                        onClick={() => setSpiTimescale(opt.v)}
                        className={`py-1.5 rounded-md text-xs font-semibold transition ${
                          spiTimescale === opt.v
                            ? 'bg-blue-900 text-white shadow-xs'
                            : 'text-slate-700 hover:bg-white/70'
                        }`}
                      >
                        {opt.lbl}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 text-xs pt-1 border-t border-slate-200">
                <span className="font-semibold text-slate-700">Ketersediaan Aktual SPI:</span>
                {spiMeta?.available ? (
                  <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold">
                    {spiMeta.min_date} s.d. {spiMeta.max_date} &bull; {spiMeta.stations_with_data} pos
                  </span>
                ) : (
                  <span className="text-[11px] px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 font-semibold">
                    Data tidak tersedia
                  </span>
                )}
              </div>

              {spiMeta?.available ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Tanggal Mulai
                    </label>
                    <input
                      type="date"
                      value={startDate}
                      min={spiMeta.min_date || undefined}
                      max={spiMeta.max_date || undefined}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white font-mono text-xs"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Tanggal Selesai
                    </label>
                    <input
                      type="date"
                      value={endDate}
                      min={spiMeta.min_date || undefined}
                      max={spiMeta.max_date || undefined}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white font-mono text-xs"
                      required
                    />
                  </div>
                </div>
              ) : (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-center gap-2">
                  <AlertTriangle size={14} className="text-amber-600 shrink-0" />
                  <span>
                    Dataset SPI {spiPeriodType} {spiTimescale} belum tersedia untuk diekspor.
                  </span>
                </div>
              )}
            </div>
          )}

          {/* 2C. FILTER PRAKIRAAN ECMWF */}
          {!loadingMeta && dataType === 'ECMWF' && (
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
              {/* Sub-filters: Resolusi & Jenis Data */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Resolusi Prakiraan
                  </span>
                  <div className="grid grid-cols-2 gap-1 p-1 rounded-lg bg-slate-200/70">
                    {['DASARIAN', 'BULANAN'].map((res) => (
                      <button
                        key={res}
                        type="button"
                        onClick={() => setEcmwfResolution(res)}
                        className={`py-1.5 rounded-md text-xs font-semibold transition ${
                          ecmwfResolution === res
                            ? 'bg-blue-900 text-white shadow-xs'
                            : 'text-slate-700 hover:bg-white/70'
                        }`}
                      >
                        {res === 'DASARIAN' ? 'Dasarian' : 'Bulanan'}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <span className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Jenis Data
                  </span>
                  <div className="grid grid-cols-2 gap-1 p-1 rounded-lg bg-slate-200/70">
                    <button
                      type="button"
                      onClick={() => setEcmwfDataType('PROBABILITAS')}
                      className={`py-1.5 rounded-md text-xs font-semibold transition ${
                        ecmwfDataType === 'PROBABILITAS'
                          ? 'bg-blue-900 text-white shadow-xs'
                          : 'text-slate-700 hover:bg-white/70'
                      }`}
                    >
                      Probabilitas (%)
                    </button>
                    <button
                      type="button"
                      onClick={() => setEcmwfDataType('DETERMINISTIK')}
                      className={`py-1.5 rounded-md text-xs font-semibold transition ${
                        ecmwfDataType === 'DETERMINISTIK'
                          ? 'bg-blue-900 text-white shadow-xs'
                          : 'text-slate-700 hover:bg-white/70'
                      }`}
                    >
                      Deterministik (mm)
                    </button>
                  </div>
                </div>
              </div>

              {/* Actual availability summary */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs pt-2 border-t border-slate-200">
                <span className="font-semibold text-slate-700">
                  Ketersediaan Aktual ({ecmwfDataType === 'DETERMINISTIK' ? 'Deterministik mm' : 'Probabilitas %'} &middot; {ecmwfResolution}):
                </span>
                {ecmwfMeta?.available ? (
                  <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold">
                    {availableEcmwfPeriods.length} periode &bull; {(ecmwfMeta.vintages || []).length} vintage aktif
                  </span>
                ) : (
                  <span className="text-[11px] px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 font-semibold">
                    Belum ada data aktif
                  </span>
                )}
              </div>

              {ecmwfMeta?.available ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Periode Target
                    </label>
                    <select
                      value={selectedPeriodId}
                      onChange={(e) => handleSelectEcmwfPeriod(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white font-mono text-xs"
                    >
                      {availableEcmwfPeriods.map((p) => (
                        <option key={p.period_id} value={p.period_id}>
                          {p.label || p.period_id} ({p.period_id})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Vintage / Issue Date (Aktif)
                    </label>
                    <select
                      value={selectedIssueDate}
                      onChange={(e) => setSelectedIssueDate(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white font-mono text-xs"
                    >
                      {availableVintagesForPeriod.map((v, idx) => (
                        <option key={v} value={v}>
                          {v} {idx === 0 ? '(Terbaru)' : '(Historis)'}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ) : (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-center gap-2">
                  <AlertTriangle size={14} className="text-amber-600 shrink-0" />
                  <span>
                    Belum ada data aktif <strong>{ecmwfDataType === 'DETERMINISTIK' ? 'Deterministik (mm)' : 'Probabilitas (%)'}</strong>{' '}
                    untuk resolusi <strong>{ecmwfResolution}</strong> di basis data. Tombol unduh dinonaktifkan.
                  </span>
                </div>
              )}
            </div>
          )}

          {/* 3. Pilihan Pos Pengamatan */}
          <div className="space-y-2">
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
              2. Pilihan Pos Pengamatan
            </label>
            <div className="grid grid-cols-3 gap-1 p-1 rounded-lg bg-slate-100 border border-slate-200">
              {[
                { v: 'ALL', lbl: `Semua Pos (${stationsMaster.length || 57})` },
                { v: 'SINGLE', lbl: 'Satu Pos' },
                { v: 'MULTI', lbl: 'Beberapa Pos' },
              ].map((opt) => (
                <button
                  key={opt.v}
                  type="button"
                  onClick={() => {
                    setStationSelectionMode(opt.v);
                    if (opt.v === 'SINGLE' && selectedStationIds.length === 0 && stationsMaster.length > 0) {
                      setSelectedStationIds([stationsMaster[0].station_id]);
                    }
                  }}
                  className={`py-1.5 rounded-md text-xs font-semibold transition ${
                    stationSelectionMode === opt.v
                      ? 'bg-blue-900 text-white shadow-xs'
                      : 'text-slate-700 hover:bg-white'
                  }`}
                >
                  {opt.lbl}
                </button>
              ))}
            </div>

            {stationSelectionMode === 'SINGLE' && (
              <select
                value={selectedStationIds[0] || ''}
                onChange={(e) => setSelectedStationIds([e.target.value])}
                className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-xs"
              >
                {stationsMaster.map((stn) => (
                  <option key={stn.station_id} value={stn.station_id}>
                    {stn.station_id} — {stn.station_name} ({stn.kabupaten})
                  </option>
                ))}
              </select>
            )}

            {stationSelectionMode === 'MULTI' && (
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-3 py-1.5 bg-slate-50 border-b border-slate-200 text-[11px]">
                  <span className="font-semibold text-slate-700">
                    {selectedStationIds.length} pos dipilih
                  </span>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setSelectedStationIds(stationsMaster.map((s) => s.station_id))}
                      className="text-blue-700 hover:underline font-semibold"
                    >
                      Pilih Semua
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedStationIds([])}
                      className="text-slate-500 hover:underline"
                    >
                      Kosongkan
                    </button>
                  </div>
                </div>
                <div className="max-h-36 overflow-y-auto p-2 grid grid-cols-1 sm:grid-cols-2 gap-1 text-xs">
                  {stationsMaster.map((stn) => (
                    <label
                      key={stn.station_id}
                      className="flex items-center gap-2 px-2 py-1 rounded hover:bg-slate-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedStationIds.includes(stn.station_id)}
                        onChange={() => handleStationToggle(stn.station_id)}
                      />
                      <span className="font-mono text-[11px] text-slate-500">{stn.station_id}</span>
                      <span className="truncate text-slate-800">{stn.station_name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 4. Format Berkas */}
          <div className="space-y-2">
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
              3. Format Berkas
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <label
                className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition ${
                  fileFormat === 'xlsx'
                    ? 'border-emerald-600 bg-emerald-50/50 ring-1 ring-emerald-600/30'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <input
                  type="radio"
                  name="exportFormat"
                  value="xlsx"
                  checked={fileFormat === 'xlsx'}
                  onChange={() => setFileFormat('xlsx')}
                />
                <FileSpreadsheet size={18} className="text-emerald-700 shrink-0" />
                <div>
                  <div className="text-xs font-bold text-slate-900">Microsoft Excel (.xlsx)</div>
                  <div className="text-[11px] text-slate-500">Header rapi &amp; siap laporan operasional</div>
                </div>
              </label>

              <label
                className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition ${
                  fileFormat === 'csv'
                    ? 'border-blue-700 bg-blue-50/50 ring-1 ring-blue-700/30'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <input
                  type="radio"
                  name="exportFormat"
                  value="csv"
                  checked={fileFormat === 'csv'}
                  onChange={() => setFileFormat('csv')}
                />
                <FileText size={18} className="text-blue-700 shrink-0" />
                <div>
                  <div className="text-xs font-bold text-slate-900">CSV (.csv UTF-8)</div>
                  <div className="text-[11px] text-slate-500">Standar tabular untuk analisis lanjutan</div>
                </div>
              </label>
            </div>
          </div>

          {downloadError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle size={15} className="shrink-0" />
              <span>{downloadError}</span>
            </div>
          )}

          {downloadSuccess && (
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
              <CheckCircle2 size={15} className="shrink-0" />
              <span>Berkas berhasil diekspor dan diunduh.</span>
            </div>
          )}
        </form>

        {/* Footer — selaras dengan RainfallInputModal */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-200 bg-slate-50/80">
          <div className="text-[11px] text-slate-500">
            Data yang dibatalkan tidak disertakan dalam ekspor aktif.
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={downloading}
              className="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-600 disabled:opacity-50"
            >
              Batal
            </button>
            <button
              type="button"
              onClick={handleExecuteDownload}
              disabled={!canSubmit}
              className="px-4 py-1.5 rounded-lg bg-blue-900 hover:bg-blue-800 text-white text-xs font-semibold inline-flex items-center gap-1.5 disabled:opacity-50"
            >
              {downloading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Memproses...</span>
                </>
              ) : (
                <>
                  <Download size={14} />
                  <span>Unduh ({fileFormat.toUpperCase()})</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
