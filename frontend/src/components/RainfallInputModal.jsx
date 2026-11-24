import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  X,
  UploadCloud,
  FileSpreadsheet,
  Keyboard,
  MapPin,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Plus,
  Trash2,
  Sliders,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';
import { API_ENDPOINTS, authFetch } from '../config';

const MONTHS_ID = [
  'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
];

const STATUS_BADGE_MAP = {
  NEW: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  IDENTICAL: 'bg-slate-100 text-slate-600 border-slate-200',
  CONFLICT: 'bg-amber-100 text-amber-800 border-amber-200',
  INVALID: 'bg-rose-100 text-rose-800 border-rose-200',
  MISSING: 'bg-sky-100 text-sky-800 border-sky-200',
  TTU: 'bg-indigo-100 text-indigo-800 border-indigo-200',
};

function generateDatesForDasarian(year, month, dasarian) {
  const y = Number(year);
  const m = Number(month);
  const d = Number(dasarian);
  if (!y || !m) return [];
  const lastDay = new Date(y, m, 0).getDate();
  let start = 1;
  let end = lastDay;
  if (d === 1) { start = 1; end = 10; }
  else if (d === 2) { start = 11; end = 20; }
  else if (d === 3) { start = 21; end = lastDay; }
  const out = [];
  for (let day = start; day <= end; day += 1) {
    out.push(`${y}-${String(m).padStart(2, '0')}-${String(day).padStart(2, '0')}`);
  }
  return out;
}

function generateDatesForRange(startStr, endStr) {
  if (!startStr || !endStr || startStr > endStr) return [];
  const out = [];
  const cur = new Date(`${startStr}T00:00:00`);
  const end = new Date(`${endStr}T00:00:00`);
  let guard = 0;
  while (cur <= end && guard < 366) {
    out.push(cur.toISOString().slice(0, 10));
    cur.setDate(cur.getDate() + 1);
    guard += 1;
  }
  return out;
}

export default function RainfallInputModal({ isOpen, onClose, onSuccess }) {
  // Wizard stages: 1=Regency, 2=Method, 3=Upload|Manual, 4=Preview, 5=Result
  const [step, setStep] = useState(1);
  const [method, setMethod] = useState(null); // 'FILE' | 'MANUAL'

  // Regencies & master stations
  const [regencies, setRegencies] = useState([]);
  const [regenciesLoading, setRegenciesLoading] = useState(false);
  const [selectedRegency, setSelectedRegency] = useState('');

  // Upload & Detection state
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [detectLoading, setDetectLoading] = useState(false);
  const [detectError, setDetectError] = useState('');
  const [detectSession, setDetectSession] = useState(null);
  const [fileConfigs, setFileConfigs] = useState({});

  // Shared default period for raw files
  const nowYear = new Date().getFullYear();
  const [sharedYear, setSharedYear] = useState(String(nowYear));
  const [sharedMonth, setSharedMonth] = useState(String(new Date().getMonth() + 1));
  const [sharedDasarian, setSharedDasarian] = useState('1');

  // Mapping Wizard modal state (inline overlay for NEEDS_MAPPING files)
  const [mappingFile, setMappingFile] = useState(null);
  const [mapProfileName, setMapProfileName] = useState('');
  const [mapOrientation, setMapOrientation] = useState('VERTICAL');
  const [mapHeaderRow, setMapHeaderRow] = useState('1');
  const [mapDateCol, setMapDateCol] = useState('1');
  const [mapStationCol, setMapStationCol] = useState('1');
  const [mapFixedStation, setMapFixedStation] = useState('');
  const [mapValueCol, setMapValueCol] = useState('2');
  const [mapSaving, setMapSaving] = useState(false);
  const [mapError, setMapError] = useState('');

  // Manual Input state
  const [manualStationId, setManualStationId] = useState('');
  const [manualPeriodMode, setManualPeriodMode] = useState('DASARIAN'); // 'DASARIAN' | 'RANGE'
  const [manualYear, setManualYear] = useState(String(nowYear));
  const [manualMonth, setManualMonth] = useState(String(new Date().getMonth() + 1));
  const [manualDasarian, setManualDasarian] = useState('1');
  const [manualStartDate, setManualStartDate] = useState(new Date().toISOString().slice(0, 10));
  const [manualEndDate, setManualEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [manualRows, setManualRows] = useState([]);

  // Preview & Commit state
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [previewData, setPreviewData] = useState(null);
  const [previewFilter, setPreviewFilter] = useState('ALL');
  const [confirmConflicts, setConfirmConflicts] = useState(false);
  const [correctionReason, setCorrectionReason] = useState('');
  const [operatorName, setOperatorName] = useState('OPERATOR_BMKG');
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitError, setCommitError] = useState('');
  const [commitResult, setCommitResult] = useState(null);

  const activeRegencyObj = useMemo(
    () => regencies.find((r) => r.code === selectedRegency) || null,
    [regencies, selectedRegency]
  );

  const loadRegencies = useCallback(async () => {
    setRegenciesLoading(true);
    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_REGENCIES);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setRegencies(json.regencies || []);
    } catch (err) {
      console.error('Failed to load regencies:', err);
    } finally {
      setRegenciesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadRegencies();
      setStep(1);
      setMethod(null);
      setSelectedRegency('');
      setSelectedFiles([]);
      setDetectSession(null);
      setFileConfigs({});
      setDetectError('');
      setPreviewData(null);
      setPreviewError('');
      setCommitResult(null);
      setCommitError('');
      setConfirmConflicts(false);
      setCorrectionReason('');
      setMappingFile(null);
    }
  }, [isOpen, loadRegencies]);

  // Auto-select first station when switching to Manual mode
  useEffect(() => {
    if (method === 'MANUAL' && activeRegencyObj?.stations?.length > 0 && !manualStationId) {
      setManualStationId(activeRegencyObj.stations[0].station_id);
    }
  }, [method, activeRegencyObj, manualStationId]);

  // Auto-generate manual date rows
  const handleGenerateManualRows = useCallback(() => {
    const dates =
      manualPeriodMode === 'DASARIAN'
        ? generateDatesForDasarian(manualYear, manualMonth, manualDasarian)
        : generateDatesForRange(manualStartDate, manualEndDate);
    setManualRows(dates.map((d) => ({ observation_date: d, raw_value: '' })));
  }, [manualPeriodMode, manualYear, manualMonth, manualDasarian, manualStartDate, manualEndDate]);

  useEffect(() => {
    if (step === 3 && method === 'MANUAL') {
      handleGenerateManualRows();
    }
  }, [step, method, handleGenerateManualRows]);

  // Multi-value Excel paste handler in manual input
  const handleManualPaste = (rowIdx, e) => {
    const text = e.clipboardData?.getData('text') || '';
    const tokens = text.split(/\r?\n|\t/).map((t) => t.trim()).filter((_, i, arr) => !(i === arr.length - 1 && arr[i] === ''));
    if (tokens.length <= 1) return;
    e.preventDefault();
    setManualRows((prev) => {
      const next = [...prev];
      tokens.forEach((val, offset) => {
        const target = rowIdx + offset;
        if (target < next.length) {
          next[target] = { ...next[target], raw_value: val };
        }
      });
      return next;
    });
  };

  // Detect uploaded files
  const handleDetectFiles = async () => {
    if (!selectedRegency || selectedFiles.length === 0) return;
    setDetectLoading(true);
    setDetectError('');
    const fd = new FormData();
    fd.append('regency_code', selectedRegency);
    selectedFiles.forEach((f) => fd.append('files', f));

    try {
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_DETECT, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setDetectSession(data);
      const initCfg = {};
      (data.files || []).forEach((f) => {
        initCfg[f.file_id] = {
          file_id: f.file_id,
          include: f.status === 'DETECTED',
          year: String(f.suggested_year || sharedYear),
          month: String(f.suggested_month || sharedMonth),
          dasarian: f.suggested_dasarian ? String(f.suggested_dasarian) : sharedDasarian,
          start_date: '',
          end_date: '',
          profile_id: f.profile_id || null,
          template_kind_override: null,
        };
      });
      setFileConfigs(initCfg);
    } catch (err) {
      setDetectError(err.message || 'Gagal mendeteksi format berkas.');
    } finally {
      setDetectLoading(false);
    }
  };

  const applySharedPeriodToRawFiles = () => {
    setFileConfigs((prev) => {
      const next = { ...prev };
      (detectSession?.files || []).forEach((f) => {
        if (f.is_raw && next[f.file_id]) {
          next[f.file_id] = {
            ...next[f.file_id],
            year: sharedYear,
            month: sharedMonth,
            dasarian: sharedDasarian,
          };
        }
      });
      return next;
    });
  };

  const handleSaveCustomProfile = async () => {
    if (!mappingFile) return;
    setMapSaving(true);
    setMapError('');
    try {
      const payload = {
        profile_name: mapProfileName || `Profil ${selectedRegency}`,
        regency_code: selectedRegency,
        structure_fingerprint: mappingFile.structure_fingerprint,
        sheet_rules: { sheet_name: mappingFile.sheetnames?.[0] || '' },
        header_config: { header_row: Number(mapHeaderRow) || 1 },
        date_config: { orientation: mapOrientation, date_col: Number(mapDateCol) || 1 },
        station_config: { station_col: Number(mapStationCol) || 1, fixed_station_id: mapFixedStation || '' },
        value_config: { value_col: Number(mapValueCol) || 2 },
        ignored_columns: [],
        symbol_mapping: {},
        operator: operatorName,
      };
      const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_PROFILES, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const saved = await res.json();
      if (!res.ok) throw new Error(saved.detail || 'Gagal menyimpan profil');

      // Update file status in session so operator can immediately preview it
      setDetectSession((prev) => ({
        ...prev,
        files: prev.files.map((f) =>
          f.file_id === mappingFile.file_id
            ? { ...f, status: 'DETECTED', template_kind: 'CUSTOM_MAPPED', profile_id: saved.profile_id, template_label: `Profil: ${saved.profile_name}`, is_raw: true }
            : f
        ),
      }));
      setFileConfigs((prev) => ({
        ...prev,
        [mappingFile.file_id]: {
          ...prev[mappingFile.file_id],
          include: true,
          profile_id: saved.profile_id,
          template_kind_override: 'CUSTOM_MAPPED',
        },
      }));
      setMappingFile(null);
    } catch (err) {
      setMapError(err.message);
    } finally {
      setMapSaving(false);
    }
  };

  // Run Preview (Step 3 -> Step 4)
  const handleRunPreview = async () => {
    setPreviewLoading(true);
    setPreviewError('');
    setConfirmConflicts(false);
    setCorrectionReason('');

    try {
      if (method === 'FILE') {
        const filesPayload = Object.values(fileConfigs).map((c) => ({
          ...c,
          year: Number(c.year),
          month: Number(c.month),
          dasarian: c.dasarian === 'ALL' ? null : Number(c.dasarian),
        }));
        const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_PREVIEW, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            batch_session_id: detectSession.batch_session_id,
            files: filesPayload,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Gagal membuat pratinjau');
        setPreviewData(data);
        setStep(4);
      } else {
        const res = await authFetch(API_ENDPOINTS.RAINFALL_V2_MANUAL_PREVIEW, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            regency_code: selectedRegency,
            station_id: manualStationId,
            rows: manualRows,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Gagal memvalidasi input manual');
        setPreviewData({
          ...data,
          preview_rows: data.items || [],
          total_preview_rows: (data.items || []).length,
        });
        setStep(4);
      }
    } catch (err) {
      setPreviewError(err.message);
    } finally {
      setPreviewLoading(false);
    }
  };

  // Commit (Step 4 -> Step 5)
  const handleCommit = async () => {
    setCommitLoading(true);
    setCommitError('');
    try {
      const endpoint = method === 'FILE' ? API_ENDPOINTS.RAINFALL_V2_COMMIT : API_ENDPOINTS.RAINFALL_V2_MANUAL_COMMIT;
      const body =
        method === 'FILE'
          ? {
              batch_session_id: detectSession.batch_session_id,
              confirm_conflicts: confirmConflicts,
              correction_reason: correctionReason,
              operator: operatorName,
            }
          : {
              regency_code: selectedRegency,
              station_id: manualStationId,
              rows: manualRows,
              confirm_conflicts: confirmConflicts,
              correction_reason: correctionReason,
              operator: operatorName,
              baseline_fingerprint: previewData?.baseline_fingerprint,
            };

      const res = await authFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Gagal menyimpan data');
      setCommitResult(result);
      setStep(5);
      if (onSuccess) onSuccess(result);
    } catch (err) {
      setCommitError(err.message);
    } finally {
      setCommitLoading(false);
    }
  };

  const filteredPreviewRows = useMemo(() => {
    const rows = previewData?.preview_rows || [];
    if (previewFilter === 'ALL') return rows;
    return rows.filter((r) => r.change_type === previewFilter || r.obs_status === previewFilter);
  }, [previewData, previewFilter]);

  if (!isOpen) return null;

  const counts = previewData?.counts || {};
  const hasConflicts = (counts.conflict || 0) > 0;
  const canCommit =
    ((counts.new || 0) > 0 || (hasConflicts && confirmConflicts)) &&
    (!confirmConflicts || correctionReason.trim().length > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-3 sm:p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
              <FileSpreadsheet size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">INPUT DATA CURAH HUJAN</h2>
              <div className="flex items-center gap-2 text-[11px] text-slate-500">
                <span>Tahap {step} / 5</span>
                {activeRegencyObj && (
                  <>
                    <span>&bull;</span>
                    <span className="font-semibold text-emerald-700">{activeRegencyObj.label}</span>
                  </>
                )}
              </div>
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

        {/* Stepper Bar */}
        <div className="grid grid-cols-5 border-b border-slate-100 bg-white px-5 py-2 text-[11px] font-medium">
          {['1. Wilayah', '2. Metode', '3. Data & Periode', '4. Pratinjau', '5. Selesai'].map((lbl, idx) => {
            const num = idx + 1;
            const active = step === num;
            const done = step > num;
            return (
              <div
                key={lbl}
                className={`text-center py-1 rounded ${
                  active ? 'bg-emerald-50 text-emerald-800 font-bold' : done ? 'text-emerald-600' : 'text-slate-400'
                }`}
              >
                {lbl}
              </div>
            );
          })}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* STEP 1: PILIH KABUPATEN/KOTA */}
          {step === 1 && (
            <div className="space-y-3.5">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Pilih Kabupaten / Kota</h3>
                <span className="text-[11px] text-slate-400">1 wilayah per sesi input</span>
              </div>
              {regenciesLoading ? (
                <div className="py-10 text-center text-xs text-slate-500">Memuat daftar wilayah...</div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {regencies.map((reg) => {
                    const selected = selectedRegency === reg.code;
                    return (
                      <button
                        key={reg.code}
                        type="button"
                        onClick={() => {
                          setSelectedRegency(reg.code);
                          setManualStationId('');
                        }}
                        className={`text-left px-4 py-3.5 rounded-lg border transition-all duration-150 ${
                          selected
                            ? 'border-emerald-600 bg-emerald-50/50 ring-1 ring-emerald-600/40 shadow-xs'
                            : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 bg-white'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <MapPin size={14} className={selected ? 'text-emerald-600 shrink-0' : 'text-slate-400 shrink-0'} />
                            <span className="font-semibold text-[13px] text-slate-800 truncate">{reg.label}</span>
                          </div>
                          {selected && <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />}
                        </div>
                        <div className="mt-2 pl-5.5 text-[11px] text-slate-500 font-medium">
                          {reg.stations_count} pos master
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* STEP 2: PILIH METODE */}
          {step === 2 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 py-4">
              <button
                type="button"
                onClick={() => {
                  setMethod('FILE');
                  setStep(3);
                }}
                className="p-6 rounded-xl border border-slate-200 hover:border-emerald-500 hover:bg-emerald-50/40 text-left transition group"
              >
                <div className="w-10 h-10 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center mb-3 group-hover:scale-105 transition">
                  <UploadCloud size={20} />
                </div>
                <div className="font-bold text-sm text-slate-900">Upload File Excel</div>
                <div className="text-xs text-slate-500 mt-1">
                  Deteksi format otomatis, multi-file (.xlsx / .xlsm), filter periode setelah deteksi.
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setMethod('MANUAL');
                  setStep(3);
                }}
                className="p-6 rounded-xl border border-slate-200 hover:border-emerald-500 hover:bg-emerald-50/40 text-left transition group"
              >
                <div className="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center mb-3 group-hover:scale-105 transition">
                  <Keyboard size={20} />
                </div>
                <div className="font-bold text-sm text-slate-900">Input Manual</div>
                <div className="text-xs text-slate-500 mt-1">
                  Pilih stasiun & dasarian/rentang tanggal, dukung paste langsung dari Excel.
                </div>
              </button>
            </div>
          )}

          {/* STEP 3A: UPLOAD FILE + AUTO DETECTION + PERIODE */}
          {step === 3 && method === 'FILE' && (
            <div className="space-y-4">
              {/* Dropzone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  if (e.dataTransfer.files?.length) {
                    setSelectedFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)]);
                    setDetectSession(null);
                  }
                }}
                className={`border-2 border-dashed rounded-xl p-5 text-center transition ${
                  isDragging ? 'border-emerald-500 bg-emerald-50/60' : 'border-slate-300 bg-slate-50/50'
                }`}
              >
                <UploadCloud size={26} className="mx-auto text-sky-600 mb-1.5" />
                <div className="text-xs font-semibold text-slate-800">
                  Seret satu atau beberapa file Excel ke sini
                </div>
                <div className="text-[11px] text-slate-500 mb-3">.xlsx atau .xlsm &bull; Maks 25 MB/file</div>
                <label className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer">
                  <span>Pilih Berkas</span>
                  <input
                    type="file"
                    multiple
                    accept=".xlsx,.xlsm"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files?.length) {
                        setSelectedFiles((prev) => [...prev, ...Array.from(e.target.files)]);
                        setDetectSession(null);
                      }
                    }}
                  />
                </label>
              </div>

              {/* Selected files chips */}
              {selectedFiles.length > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-50 border border-slate-200 rounded-lg p-2.5">
                  <div className="flex flex-wrap gap-1.5">
                    {selectedFiles.map((f, i) => (
                      <span
                        key={`${f.name}-${i}`}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-white border border-slate-200 text-[11px] font-mono text-slate-700"
                      >
                        <FileSpreadsheet size={12} className="text-emerald-600" />
                        {f.name}
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedFiles((prev) => prev.filter((_, idx) => idx !== i));
                            setDetectSession(null);
                          }}
                          className="text-slate-400 hover:text-rose-600 font-bold"
                        >
                          &times;
                        </button>
                      </span>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={handleDetectFiles}
                    disabled={detectLoading}
                    className="px-3.5 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {detectLoading ? <RefreshCw size={13} className="animate-spin" /> : <Sliders size={13} />}
                    <span>{detectLoading ? 'Mendeteksi...' : 'Deteksi Format Otomatis'}</span>
                  </button>
                </div>
              )}

              {detectError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <AlertCircle size={15} />
                  <span>{detectError}</span>
                </div>
              )}

              {/* Detection Results + Period Selection (ONLY shown AFTER detection) */}
              {detectSession && (
                <div className="space-y-3">
                  {/* Shared Period Bar for Raw Files */}
                  {detectSession.files.some((f) => f.is_raw && f.status === 'DETECTED') && (
                    <div className="flex flex-wrap items-center gap-2 bg-emerald-50/60 border border-emerald-200 rounded-lg p-3 text-xs">
                      <span className="font-bold text-emerald-900">Periode Bersama:</span>
                      <select
                        value={sharedMonth}
                        onChange={(e) => setSharedMonth(e.target.value)}
                        className="px-2 py-1 rounded border border-slate-300 bg-white text-xs"
                      >
                        {MONTHS_ID.map((m, idx) => (
                          <option key={m} value={idx + 1}>{m}</option>
                        ))}
                      </select>
                      <input
                        type="number"
                        value={sharedYear}
                        onChange={(e) => setSharedYear(e.target.value)}
                        className="w-20 px-2 py-1 rounded border border-slate-300 bg-white text-xs font-mono"
                      />
                      <select
                        value={sharedDasarian}
                        onChange={(e) => setSharedDasarian(e.target.value)}
                        className="px-2 py-1 rounded border border-slate-300 bg-white text-xs"
                      >
                        <option value="1">Dasarian I (1–10)</option>
                        <option value="2">Dasarian II (11–20)</option>
                        <option value="3">Dasarian III (21–Akhir)</option>
                        <option value="ALL">Seluruh Bulan</option>
                      </select>
                      <button
                        type="button"
                        onClick={applySharedPeriodToRawFiles}
                        className="px-2.5 py-1 rounded bg-emerald-700 text-white text-[11px] font-semibold hover:bg-emerald-800"
                      >
                        Terapkan ke Semua
                      </button>
                    </div>
                  )}

                  {/* Per-File Detection Cards */}
                  <div className="space-y-2.5">
                    {detectSession.files.map((f) => {
                      const cfg = fileConfigs[f.file_id] || {};
                      const isOk = f.status === 'DETECTED';
                      return (
                        <div
                          key={f.file_id}
                          className={`rounded-lg border p-3 ${
                            isOk ? 'border-slate-200 bg-white' : 'border-amber-200 bg-amber-50/40'
                          }`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                checked={!!cfg.include}
                                disabled={!isOk}
                                onChange={(e) =>
                                  setFileConfigs((prev) => ({
                                    ...prev,
                                    [f.file_id]: { ...prev[f.file_id], include: e.target.checked },
                                  }))
                                }
                              />
                              <span className="font-mono text-xs font-bold text-slate-800">{f.filename}</span>
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  isOk ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                                }`}
                              >
                                {f.template_label}
                              </span>
                            </div>

                            {f.status === 'NEEDS_MAPPING' && (
                              <button
                                type="button"
                                onClick={() => {
                                  setMappingFile(f);
                                  setMapProfileName(`Profil ${selectedRegency}`);
                                  setMapError('');
                                }}
                                className="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-700 text-white text-[11px] font-semibold"
                              >
                                Buka Mapping Wizard
                              </button>
                            )}
                          </div>

                          {f.error_reason && (
                            <div className="mt-2 text-[11px] text-rose-700 flex items-start gap-1.5">
                              <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                              <span>{f.error_reason}</span>
                            </div>
                          )}

                          {f.metadata_conflicts?.length > 0 && (
                            <div className="mt-2 p-2 rounded bg-amber-50 border border-amber-200 text-[11px] text-amber-900">
                              {f.metadata_conflicts.map((c, idx) => (
                                <div key={idx} className="flex items-start gap-1.5">
                                  <AlertTriangle size={13} className="shrink-0 mt-0.5 text-amber-600" />
                                  <span>{c}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Period Controls AFTER Detection */}
                          {isOk && cfg.include && (
                            <div className="mt-2.5 pt-2.5 border-t border-slate-100 flex flex-wrap items-center gap-2 text-xs">
                              {f.is_raw ? (
                                <>
                                  <span className="text-[11px] font-semibold text-slate-600">Periode File:</span>
                                  <select
                                    value={cfg.month}
                                    onChange={(e) =>
                                      setFileConfigs((prev) => ({
                                        ...prev,
                                        [f.file_id]: { ...prev[f.file_id], month: e.target.value },
                                      }))
                                    }
                                    className="px-2 py-1 rounded border border-slate-300 text-xs"
                                  >
                                    {MONTHS_ID.map((m, idx) => (
                                      <option key={m} value={idx + 1}>{m}</option>
                                    ))}
                                  </select>
                                  <input
                                    type="number"
                                    value={cfg.year}
                                    onChange={(e) =>
                                      setFileConfigs((prev) => ({
                                        ...prev,
                                        [f.file_id]: { ...prev[f.file_id], year: e.target.value },
                                      }))
                                    }
                                    className="w-20 px-2 py-1 rounded border border-slate-300 text-xs font-mono"
                                  />
                                  <select
                                    value={cfg.dasarian}
                                    onChange={(e) =>
                                      setFileConfigs((prev) => ({
                                        ...prev,
                                        [f.file_id]: { ...prev[f.file_id], dasarian: e.target.value },
                                      }))
                                    }
                                    className="px-2 py-1 rounded border border-slate-300 text-xs"
                                  >
                                    <option value="1">Dasarian I (1–10)</option>
                                    <option value="2">Dasarian II (11–20)</option>
                                    <option value="3">Dasarian III (21–Akhir)</option>
                                    <option value="ALL">Seluruh Bulan</option>
                                  </select>
                                </>
                              ) : (
                                <>
                                  <span className="text-[11px] font-semibold text-slate-600">Filter Rentang (Opsional):</span>
                                  <input
                                    type="date"
                                    value={cfg.start_date || ''}
                                    onChange={(e) =>
                                      setFileConfigs((prev) => ({
                                        ...prev,
                                        [f.file_id]: { ...prev[f.file_id], start_date: e.target.value },
                                      }))
                                    }
                                    className="px-2 py-1 rounded border border-slate-300 text-xs font-mono"
                                  />
                                  <span className="text-slate-400">s/d</span>
                                  <input
                                    type="date"
                                    value={cfg.end_date || ''}
                                    onChange={(e) =>
                                      setFileConfigs((prev) => ({
                                        ...prev,
                                        [f.file_id]: { ...prev[f.file_id], end_date: e.target.value },
                                      }))
                                    }
                                    className="px-2 py-1 rounded border border-slate-300 text-xs font-mono"
                                  />
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Inline Mapping Wizard */}
              {mappingFile && (
                <div className="rounded-xl border-2 border-amber-400 bg-amber-50/40 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-slate-900">Mapping Wizard — {mappingFile.filename}</h4>
                    <button type="button" onClick={() => setMappingFile(null)} className="text-xs text-slate-500 hover:text-slate-800">
                      Tutup
                    </button>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Nama Profil</label>
                      <input value={mapProfileName} onChange={(e) => setMapProfileName(e.target.value)} className="w-full px-2 py-1 rounded border border-slate-300 bg-white" />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Orientasi Tanggal</label>
                      <select value={mapOrientation} onChange={(e) => setMapOrientation(e.target.value)} className="w-full px-2 py-1 rounded border border-slate-300 bg-white">
                        <option value="VERTICAL">Vertikal (per baris)</option>
                        <option value="HORIZONTAL">Horizontal (per kolom)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Baris Header (1-based)</label>
                      <input type="number" value={mapHeaderRow} onChange={(e) => setMapHeaderRow(e.target.value)} className="w-full px-2 py-1 rounded border border-slate-300 bg-white" />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Kolom Tanggal / Stasiun</label>
                      <input type="number" value={mapOrientation === 'VERTICAL' ? mapDateCol : mapStationCol} onChange={(e) => (mapOrientation === 'VERTICAL' ? setMapDateCol(e.target.value) : setMapStationCol(e.target.value))} className="w-full px-2 py-1 rounded border border-slate-300 bg-white" />
                    </div>
                    {mapOrientation === 'VERTICAL' && (
                      <>
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Kolom Nilai CH</label>
                          <input type="number" value={mapValueCol} onChange={(e) => setMapValueCol(e.target.value)} className="w-full px-2 py-1 rounded border border-slate-300 bg-white" />
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Stasiun Tetap (Opsional)</label>
                          <select value={mapFixedStation} onChange={(e) => setMapFixedStation(e.target.value)} className="w-full px-2 py-1 rounded border border-slate-300 bg-white">
                            <option value="">-- Baca dari kolom --</option>
                            {(activeRegencyObj?.stations || []).map((s) => (
                              <option key={s.station_id} value={s.station_id}>{s.station_name}</option>
                            ))}
                          </select>
                        </div>
                      </>
                    )}
                  </div>

                  {mappingFile.preview_grid?.length > 0 && (
                    <div className="overflow-x-auto max-h-36 border border-slate-200 rounded bg-white">
                      <table className="w-full text-[10px] font-mono">
                        <tbody>
                          {mappingFile.preview_grid.slice(0, 8).map((row, rIdx) => (
                            <tr key={rIdx} className="border-b border-slate-100">
                              <td className="px-1.5 py-0.5 bg-slate-100 text-slate-500">{rIdx + 1}</td>
                              {row.slice(0, 10).map((cell, cIdx) => (
                                <td key={cIdx} className="px-1.5 py-0.5 border-l border-slate-100 truncate max-w-[90px]">{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {mapError && <div className="text-xs text-rose-700">{mapError}</div>}
                  <div className="flex justify-end">
                    <button
                      type="button"
                      disabled={mapSaving}
                      onClick={handleSaveCustomProfile}
                      className="px-3.5 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold"
                    >
                      {mapSaving ? 'Menyimpan...' : 'Simpan Profil Mapping'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 3B: INPUT MANUAL MULTI-TANGGAL */}
          {step === 3 && method === 'MANUAL' && (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Stasiun Master</label>
                  <select
                    value={manualStationId}
                    onChange={(e) => setManualStationId(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs"
                  >
                    {(activeRegencyObj?.stations || []).map((s) => (
                      <option key={s.station_id} value={s.station_id}>
                        {s.station_name} ({s.station_id})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Mode Periode</label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setManualPeriodMode('DASARIAN')}
                      className={`flex-1 py-1.5 rounded border text-xs font-semibold ${
                        manualPeriodMode === 'DASARIAN' ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-white text-slate-700 border-slate-300'
                      }`}
                    >
                      Dasarian
                    </button>
                    <button
                      type="button"
                      onClick={() => setManualPeriodMode('RANGE')}
                      className={`flex-1 py-1.5 rounded border text-xs font-semibold ${
                        manualPeriodMode === 'RANGE' ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-white text-slate-700 border-slate-300'
                      }`}
                    >
                      Rentang Tanggal
                    </button>
                  </div>
                </div>

                {manualPeriodMode === 'DASARIAN' ? (
                  <div className="sm:col-span-2 flex flex-wrap items-center gap-2">
                    <select value={manualMonth} onChange={(e) => setManualMonth(e.target.value)} className="px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs">
                      {MONTHS_ID.map((m, idx) => (
                        <option key={m} value={idx + 1}>{m}</option>
                      ))}
                    </select>
                    <input type="number" value={manualYear} onChange={(e) => setManualYear(e.target.value)} className="w-24 px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs font-mono" />
                    <select value={manualDasarian} onChange={(e) => setManualDasarian(e.target.value)} className="px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs">
                      <option value="1">Dasarian I (1–10)</option>
                      <option value="2">Dasarian II (11–20)</option>
                      <option value="3">Dasarian III (21–Akhir)</option>
                      <option value="0">1 Bulan Penuh</option>
                    </select>
                  </div>
                ) : (
                  <div className="sm:col-span-2 flex flex-wrap items-center gap-2">
                    <input type="date" value={manualStartDate} onChange={(e) => setManualStartDate(e.target.value)} className="px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs font-mono" />
                    <span className="text-slate-400">s/d</span>
                    <input type="date" value={manualEndDate} onChange={(e) => setManualEndDate(e.target.value)} className="px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs font-mono" />
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>Tip: Paste langsung kolom dari Excel. Kosong = tidak disimpan. Simbol: <code>0</code>, <code>TTU</code>, <code>X</code>.</span>
                <button
                  type="button"
                  onClick={() => setManualRows((prev) => [...prev, { observation_date: manualEndDate, raw_value: '' }])}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 font-semibold"
                >
                  <Plus size={12} /> Tambah Baris
                </button>
              </div>

              <div className="max-h-64 overflow-y-auto border border-slate-200 rounded-lg">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 sticky top-0 border-b border-slate-200 text-slate-600">
                    <tr>
                      <th className="py-2 px-3 text-left w-40">Tanggal</th>
                      <th className="py-2 px-3 text-left">Nilai CH (mm / Simbol)</th>
                      <th className="py-2 px-3 text-left w-36">Cepat</th>
                      <th className="py-2 px-2 w-10"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {manualRows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/70">
                        <td className="py-1.5 px-3">
                          <input
                            type="date"
                            value={row.observation_date}
                            onChange={(e) =>
                              setManualRows((prev) => prev.map((r, i) => (i === idx ? { ...r, observation_date: e.target.value } : r)))
                            }
                            className="px-2 py-1 rounded border border-slate-200 font-mono text-xs"
                          />
                        </td>
                        <td className="py-1.5 px-3">
                          <input
                            type="text"
                            value={row.raw_value}
                            placeholder="Kosong (dilewati)"
                            onPaste={(e) => handleManualPaste(idx, e)}
                            onChange={(e) =>
                              setManualRows((prev) => prev.map((r, i) => (i === idx ? { ...r, raw_value: e.target.value } : r)))
                            }
                            className="w-full px-2.5 py-1 rounded border border-slate-200 font-mono text-xs focus:border-emerald-500 focus:outline-none"
                          />
                        </td>
                        <td className="py-1.5 px-3">
                          <div className="flex gap-1">
                            {['0', 'TTU', 'X'].map((sym) => (
                              <button
                                key={sym}
                                type="button"
                                onClick={() =>
                                  setManualRows((prev) => prev.map((r, i) => (i === idx ? { ...r, raw_value: sym } : r)))
                                }
                                className="px-1.5 py-0.5 rounded bg-slate-100 hover:bg-emerald-100 text-[10px] font-mono font-semibold text-slate-700"
                              >
                                {sym}
                              </button>
                            ))}
                          </div>
                        </td>
                        <td className="py-1.5 px-2 text-center">
                          <button
                            type="button"
                            onClick={() => setManualRows((prev) => prev.filter((_, i) => i !== idx))}
                            className="text-slate-400 hover:text-rose-600"
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {previewError && step === 3 && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle size={15} />
              <span>{previewError}</span>
            </div>
          )}

          {/* STEP 4: VALIDASI & PRATINJAU */}
          {step === 4 && previewData && (
            <div className="space-y-4">
              {/* Summary Metrics */}
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                {[
                  { k: 'NEW', label: 'Baru', val: counts.new || 0, cls: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
                  { k: 'CONFLICT', label: 'Konflik', val: counts.conflict || 0, cls: 'text-amber-700 bg-amber-50 border-amber-200' },
                  { k: 'IDENTICAL', label: 'Identik', val: counts.identical || 0, cls: 'text-slate-600 bg-slate-50 border-slate-200' },
                  { k: 'INVALID', label: 'Invalid', val: counts.invalid || 0, cls: 'text-rose-700 bg-rose-50 border-rose-200' },
                  { k: 'TTU', label: 'TTU', val: counts.ttu || 0, cls: 'text-indigo-700 bg-indigo-50 border-indigo-200' },
                  { k: 'MISSING', label: 'Missing', val: counts.missing || 0, cls: 'text-sky-700 bg-sky-50 border-sky-200' },
                ].map((m) => (
                  <button
                    key={m.k}
                    type="button"
                    onClick={() => setPreviewFilter((prev) => (prev === m.k ? 'ALL' : m.k))}
                    className={`p-2.5 rounded-lg border text-left transition ${m.cls} ${previewFilter === m.k ? 'ring-2 ring-slate-400' : ''}`}
                  >
                    <div className="text-[10px] font-semibold uppercase opacity-80">{m.label}</div>
                    <div className="text-base font-bold font-mono">{m.val}</div>
                  </button>
                ))}
              </div>

              {/* Per-file coverage summary */}
              {previewData.file_summaries?.length > 0 && (
                <div className="space-y-1.5">
                  {previewData.file_summaries.map((fs) => (
                    <div key={fs.file_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-[11px]">
                      <span className="font-mono font-bold text-slate-800">{fs.filename}</span>
                      <div className="flex flex-wrap items-center gap-2 text-slate-600">
                        <span>{fs.recognized_stations_count} stasiun</span>
                        <span>&bull;</span>
                        <span>{fs.records_count} observasi</span>
                        {fs.date_coverage?.start && (
                          <>
                            <span>&bull;</span>
                            <span className="font-mono">{fs.date_coverage.start} s/d {fs.date_coverage.end}</span>
                          </>
                        )}
                        {fs.out_of_range_count > 0 && (
                          <span className="text-slate-400">({fs.out_of_range_count} di luar rentang)</span>
                        )}
                        {fs.unmapped_stations?.length > 0 && (
                          <span className="text-amber-700 font-semibold">{fs.unmapped_stations.length} pos belum cocok</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Preview Table */}
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200 text-xs">
                  <span className="font-semibold text-slate-700">
                    Pratinjau ({filteredPreviewRows.length} / {previewData.total_preview_rows} baris)
                  </span>
                  {previewFilter !== 'ALL' && (
                    <button type="button" onClick={() => setPreviewFilter('ALL')} className="text-sky-700 hover:underline text-[11px]">
                      Reset Filter ({previewFilter})
                    </button>
                  )}
                </div>
                <div className="max-h-52 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-white sticky top-0 border-b border-slate-200 text-slate-500 text-[11px]">
                      <tr>
                        <th className="py-1.5 px-2.5 text-left">Tanggal</th>
                        <th className="py-1.5 px-2.5 text-left">Stasiun</th>
                        <th className="py-1.5 px-2.5 text-right">Baru</th>
                        <th className="py-1.5 px-2.5 text-right">DB Lama</th>
                        <th className="py-1.5 px-2.5 text-center">Status Obs</th>
                        <th className="py-1.5 px-2.5 text-center">Kategori</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredPreviewRows.slice(0, 100).map((r, i) => (
                        <tr key={i}>
                          <td className="py-1.5 px-2.5 font-mono">{r.observation_date}</td>
                          <td className="py-1.5 px-2.5 truncate max-w-[180px]" title={r.station_id}>{r.station_name}</td>
                          <td className="py-1.5 px-2.5 text-right font-mono font-semibold text-slate-900">
                            {r.display_value || (r.obs_status === 'OBSERVED_ZERO' ? '-' : r.obs_status === 'TTU' ? 'TTU' : (r.obs_status === 'MISSING' || r.obs_status === 'DAMAGED' || r.rainfall_mm === null) ? '9999' : `${r.rainfall_mm}`)}
                          </td>
                          <td className="py-1.5 px-2.5 text-right font-mono text-slate-500">
                            {r.old_obs_status === 'OBSERVED_ZERO'
                              ? '-'
                              : r.old_obs_status === 'TTU'
                                ? 'TTU'
                                : (r.old_obs_status === 'MISSING' || r.old_obs_status === 'DAMAGED')
                                  ? '9999'
                                  : (r.old_rainfall_mm !== null && r.old_rainfall_mm !== undefined ? `${r.old_rainfall_mm}` : '—')}
                          </td>
                          <td className="py-1.5 px-2.5 text-center font-mono text-[10px]">{r.obs_status}</td>
                          <td className="py-1.5 px-2.5 text-center">
                            <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${STATUS_BADGE_MAP[r.change_type] || 'bg-slate-100'}`}>
                              {r.change_type}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Operator & Conflict Approval */}
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3.5 space-y-3 text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">Operator</label>
                    <input
                      value={operatorName}
                      onChange={(e) => setOperatorName(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">
                      Alasan Koreksi {confirmConflicts ? '(Wajib)' : '(Opsional)'}
                    </label>
                    <input
                      value={correctionReason}
                      onChange={(e) => setCorrectionReason(e.target.value)}
                      placeholder="Misal: Pembaruan laporan dasarian stasiun..."
                      className="w-full px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs"
                    />
                  </div>
                </div>

                {hasConflicts && (
                  <label className="flex items-center gap-2 p-2.5 rounded border border-amber-300 bg-amber-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={confirmConflicts}
                      onChange={(e) => setConfirmConflicts(e.target.checked)}
                    />
                    <span className="font-semibold text-amber-900">
                      Setujui pembaruan {counts.conflict} data konflik (tercatat di audit log)
                    </span>
                  </label>
                )}
              </div>

              {commitError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <AlertCircle size={15} />
                  <span>{commitError}</span>
                </div>
              )}
            </div>
          )}

          {/* STEP 5: HASIL */}
          {step === 5 && commitResult && (
            <div className="py-6 text-center space-y-4">
              <CheckCircle2 size={44} className="mx-auto text-emerald-600" />
              <div>
                <h3 className="text-base font-bold text-slate-900">Data Curah Hujan Tersimpan</h3>
                <p className="text-xs text-slate-600 mt-1">{commitResult.message}</p>
              </div>
              <div className="max-w-sm mx-auto bg-slate-50 border border-slate-200 rounded-lg p-3.5 text-xs space-y-1.5 text-left">
                <div className="flex justify-between"><span className="text-slate-500">Batch ID</span><span className="font-mono font-bold">{commitResult.batch_id}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Data Baru</span><span className="font-mono font-bold text-emerald-700">+{commitResult.records_added}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Koreksi</span><span className="font-mono font-bold text-amber-700">{commitResult.records_updated}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Identik Dilewati</span><span className="font-mono text-slate-600">{commitResult.records_identical_skipped}</span></div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-200 bg-slate-50/80">
          {step > 1 && step < 5 ? (
            <button
              type="button"
              onClick={() => setStep((s) => s - 1)}
              className="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 flex items-center gap-1.5"
            >
              <ArrowLeft size={13} /> Kembali
            </button>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2">
            {step < 5 && (
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-200/60"
              >
                Batal
              </button>
            )}

            {step === 1 && (
              <button
                type="button"
                disabled={!selectedRegency}
                onClick={() => setStep(2)}
                className="px-4 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              >
                Lanjut <ArrowRight size={13} />
              </button>
            )}

            {step === 3 && (
              <button
                type="button"
                disabled={
                  previewLoading ||
                  (method === 'FILE'
                    ? !detectSession || !Object.values(fileConfigs).some((c) => c.include)
                    : !manualStationId || manualRows.every((r) => !String(r.raw_value || '').trim()))
                }
                onClick={handleRunPreview}
                className="px-4 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              >
                {previewLoading ? 'Memvalidasi...' : 'Pratinjau & Validasi'} <ArrowRight size={13} />
              </button>
            )}

            {step === 4 && (
              <button
                type="button"
                disabled={commitLoading || !canCommit}
                onClick={handleCommit}
                className="px-4 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              >
                <ShieldCheck size={14} />
                <span>{commitLoading ? 'Menyimpan...' : 'Simpan ke Database'}</span>
              </button>
            )}

            {step === 5 && (
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold"
              >
                Selesai
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
